"""Read the staged drop tables into the drops each npc has."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import DropTableKind, RelationshipType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, numbers, whole
from wiki_api.pipeline.sources.errors import MalformedSourceValue
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredConfig(name="drop_tables.json")
IDS_FIELD: Final = "ids"
ID_FIELD: Final = "id"
WEIGHT_FIELD: Final = "weight"
MIN_FIELD: Final = "minAmount"
MAX_FIELD: Final = "maxAmount"
DESCRIPTION_FIELD: Final = "description"
GUARANTEED: Final = DropTableKind.DEFAULT
SECTIONS: Final = (
    DropTableKind.DEFAULT,
    DropTableKind.MAIN,
    DropTableKind.CHARM,
    DropTableKind.TERTIARY,
)
GUARANTEED_NOTE: Final = (
    "a row in the always-dropped table is recorded as certain, because the game "
    "hands it over without rolling"
)


class _Roll:
    def __init__(self, item_id: int, weight: float, low: int, high: int) -> None:
        self.item_id = item_id
        self.weight = weight
        self.low = low
        self.high = high

    def joined(self, other: _Roll) -> _Roll:
        return _Roll(
            self.item_id,
            self.weight + other.weight,
            min(self.low, other.low),
            max(self.high, other.high),
        )


def read_drops(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Turn every table row into a drop edge for every npc the table serves."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    folded = 0
    for table in staged.records(DECLARED):
        owners = _owners(table, known, skipped)
        for section in SECTIONS:
            rolls, dropped, joined = _rolls(table, section, known, skipped)
            folded += joined
            skipped.extend(dropped)
            total = sum(roll.weight for roll in rolls)
            for owner in owners:
                edges.extend(_edges(owner, table, section, rolls, total))
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, edges),
        skipped=tuple(skipped),
        notes=(
            GUARANTEED_NOTE,
            f"{folded} rows folded into an earlier row for the same item",
        ),
    )


def _owners(
    table: Mapping[str, Any], known: frozenset[EntityKey], skipped: list[Skipped]
) -> tuple[EntityKey, ...]:
    owners: list[EntityKey] = []
    for npc_id in numbers(table.get(IDS_FIELD), DECLARED.name, "table", IDS_FIELD):
        key = EntityKey(type=EntityType.NPC, id=npc_id)
        if key in known:
            owners.append(key)
        else:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(key),
                )
            )
    return tuple(owners)


def _rolls(
    table: Mapping[str, Any],
    section: DropTableKind,
    known: frozenset[EntityKey],
    skipped: list[Skipped],
) -> tuple[tuple[_Roll, ...], list[Skipped], int]:
    rows = table.get(section.value) or []
    dropped: list[Skipped] = []
    ordered: list[_Roll] = []
    at: dict[int, int] = {}
    folded = 0
    for row in rows:
        item_id = int(str(row[ID_FIELD]))
        item = EntityKey(type=EntityType.ITEM, id=item_id)
        weight = _weight(row, item_id)
        if item not in known:
            dropped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(item),
                )
            )
            continue
        if weight <= 0:
            dropped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.NO_CHANCE,
                    detail=str(item),
                )
            )
            continue
        roll = _Roll(
            item_id,
            weight,
            _amount(row, item_id, MIN_FIELD),
            _amount(row, item_id, MAX_FIELD),
        )
        seen = at.get(item_id)
        if seen is None:
            at[item_id] = len(ordered)
            ordered.append(roll)
        else:
            ordered[seen] = ordered[seen].joined(roll)
            folded += 1
    return tuple(ordered), dropped, folded


def _weight(row: Mapping[str, Any], item_id: int) -> float:
    raw = row.get(WEIGHT_FIELD)
    try:
        return float(str(raw))
    except ValueError as error:
        raise MalformedSourceValue(
            DECLARED.name, str(item_id), WEIGHT_FIELD, f"{raw!r}"
        ) from error


def _amount(row: Mapping[str, Any], item_id: int, field: str) -> int:
    read = whole(row.get(field), DECLARED.name, str(item_id), field)
    return read if read is not None else 1


def _edges(
    owner: EntityKey,
    table: Mapping[str, Any],
    section: DropTableKind,
    rolls: Sequence[_Roll],
    total: float,
) -> list[dict[str, Any]]:
    return [
        {
            "src": str(owner),
            "rel": RelationshipType.DROPS.value,
            "dst": str(EntityKey(type=EntityType.ITEM, id=roll.item_id)),
            "order_key": round(_denominator(roll, section, total) / roll.weight),
            "source_ref": f"{DECLARED.name}#{table.get(IDS_FIELD)}.{section.value}",
            "attributes": {
                "weight": roll.weight,
                "denominator": _denominator(roll, section, total),
                "table_kind": section.value,
                "min_amount": roll.low,
                "max_amount": roll.high,
            },
        }
        for roll in rolls
    ]


def _denominator(roll: _Roll, section: DropTableKind, total: float) -> float:
    return roll.weight if section is GUARANTEED else total


def _document(
    staged: StagedSources, edges: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": DECLARED.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CONFIG.value,
                "source_file": DECLARED.name,
                "game_version": str(staged.game_version(DECLARED.staged)),
                "edges": list(edges),
            },
        }
    )


# test cases


def _row(item_id: int, weight: str, low: str = "1", high: str = "1") -> dict[str, str]:
    return {
        "id": str(item_id),
        "weight": weight,
        "minAmount": low,
        "maxAmount": high,
    }


def _sources(tmp_path: Any, tables: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(tmp_path, {DECLARED.staged: json.dumps(tables)})


def _known() -> frozenset[EntityKey]:
    return frozenset(
        {EntityKey(type=EntityType.NPC, id=50)}
        | {EntityKey(type=EntityType.ITEM, id=item) for item in (536, 995, 1149)}
    )


def test_a_weighted_row_is_measured_against_its_own_table(tmp_path: Any) -> None:
    table = {
        "ids": "50",
        "default": [],
        "charm": [],
        "main": [_row(995, "37.0"), _row(1149, "3.0")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    coins = outcome.read.document.edges[0]
    assert coins.attributes["weight"] == 37.0
    assert coins.attributes["denominator"] == 40.0
    assert coins.order_key == 1


def test_an_always_dropped_row_is_recorded_as_certain(tmp_path: Any) -> None:
    table = {"ids": "50", "default": [_row(536, "100.0")], "charm": [], "main": []}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    bones = outcome.read.document.edges[0]
    assert bones.attributes["weight"] == bones.attributes["denominator"]
    assert bones.order_key == 1


def test_one_table_serving_many_npcs_gives_each_of_them_the_drop(
    tmp_path: Any,
) -> None:
    table = {"ids": "50,51", "default": [], "charm": [], "main": [_row(995, "1.0")]}
    known = _known() | {EntityKey(type=EntityType.NPC, id=51)}
    outcome = read_drops(_sources(tmp_path, [table]), known)
    assert {edge.src.id for edge in outcome.read.document.edges} == {50, 51}


def test_two_rows_for_one_item_in_one_table_become_one_drop(tmp_path: Any) -> None:
    table = {
        "ids": "50",
        "default": [],
        "charm": [],
        "main": [_row(995, "37.0", "3", "3"), _row(995, "9.0", "5", "5")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert outcome.edges == 1
    coins = outcome.read.document.edges[0]
    assert coins.attributes["weight"] == 46.0
    assert coins.attributes["min_amount"] == 3
    assert coins.attributes["max_amount"] == 5


def test_a_row_that_can_never_be_rolled_is_dropped_and_counted(tmp_path: Any) -> None:
    table = {"ids": "50", "default": [], "charm": [], "main": [_row(995, "0.0")]}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"no_chance": 1}


def test_a_table_for_an_npc_nothing_defines_is_dropped_and_counted(
    tmp_path: Any,
) -> None:
    table = {"ids": "2124", "default": [], "charm": [], "main": [_row(995, "1.0")]}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_a_row_for_an_item_nothing_defines_is_dropped_and_counted(
    tmp_path: Any,
) -> None:
    table = {"ids": "50", "default": [], "charm": [], "main": [_row(4242, "1.0")]}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_each_table_of_one_npc_is_kept_apart(tmp_path: Any) -> None:
    table = {
        "ids": "50",
        "default": [_row(536, "100.0")],
        "charm": [],
        "main": [_row(995, "1.0")],
        "tertiary": [_row(1149, "1.0")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    kinds = {edge.attributes["table_kind"] for edge in outcome.read.document.edges}
    assert kinds == {DropTableKind.DEFAULT, DropTableKind.MAIN, DropTableKind.TERTIARY}


def test_a_weight_that_is_not_a_number_stops_the_build(tmp_path: Any) -> None:
    import pytest

    table = {"ids": "50", "default": [], "charm": [], "main": [_row(995, "often")]}
    with pytest.raises(MalformedSourceValue):
        read_drops(_sources(tmp_path, [table]), _known())
