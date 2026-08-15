"""Read the staged drop tables into the drops each npc has."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import DropTableKind, RelationshipType
from wiki_api.domain.vocabulary import ClueLevel, SharedDropTable, SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, numbers, whole
from wiki_api.pipeline.sources.errors import MalformedSourceValue, UnreadableSlot
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import (
    DECLARED_CONSTANTS,
    DECLARED_SHARED_TABLES,
    DeclaredConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources
    from wiki_api.pipeline.staging.shared import SharedTable

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

#: What each id `WeightBasedTable.kt` reserves stands for instead of an item.
NOTHING_SYMBOL: Final = "Items.DWARF_REMAINS_0"
CLUE_SYMBOLS: Final[Mapping[str, ClueLevel]] = {
    "Items.TOOLKIT_1": ClueLevel.EASY,
    "Items.ROTTEN_POTATO_5733": ClueLevel.MEDIUM,
    "Items.GRANITE_LOBSTER_POUCH_12070": ClueLevel.HARD,
}
TABLE_SYMBOLS: Final[Mapping[str, SharedDropTable]] = {
    "Items.TINDERBOX_31": SharedDropTable.RARE,
    "Items.NULL_799": SharedDropTable.CELE_MINOR,
    "Items.SACRED_CLAY_POUCH_CLASS_1_14422": SharedDropTable.UNCOMMON_SEED,
    "Items.SACRED_CLAY_POUCH_CLASS_2_14424": SharedDropTable.HERB,
    "Items.SACRED_CLAY_POUCH_CLASS_3_14426": SharedDropTable.GEM,
    "Items.SACRED_CLAY_POUCH_CLASS_4_14428": SharedDropTable.RARE_SEED,
    "Items.SACRED_CLAY_POUCH_CLASS_5_14430": SharedDropTable.ALLOTMENT_SEED,
}
GUARANTEED_NOTE: Final = (
    "a row in the always-dropped table is recorded as certain, because the game "
    "hands it over without rolling"
)
SLOT_NOTE: Final = (
    "a row naming one of the ids WeightBasedTable.kt reserves is an instruction, "
    "not an item: it is either nothing at all, a treasure trail, or a roll on a "
    "table many npcs share"
)


@dataclass(frozen=True)
class _Slot:
    """What a reserved id stands for in place of an item."""

    clue: ClueLevel | None = None
    table: SharedDropTable | None = None


@dataclass(frozen=True)
class Reserved:
    """Every id the game reserves, and the tables the reserved ones roll on."""

    slots: Mapping[int, _Slot]
    tables: Mapping[SharedDropTable, SharedTable]

    @classmethod
    def of(cls, staged: StagedSources) -> Reserved:
        present = [one for one in DECLARED_CONSTANTS if staged.has_staged(one.staged)]
        if not present:
            return cls(slots={}, tables={})
        lookup = staged.constants(present)
        slots: dict[int, _Slot] = {}
        for symbol in (NOTHING_SYMBOL, *CLUE_SYMBOLS, *TABLE_SYMBOLS):
            found = lookup.id_of(symbol)
            if found is None:
                raise UnreadableSlot(DECLARED.name, symbol)
            slots[found] = _Slot(
                clue=CLUE_SYMBOLS.get(symbol), table=TABLE_SYMBOLS.get(symbol)
            )
        return cls(
            slots=slots,
            tables={
                SharedDropTable(one.name): staged.shared_table(one)
                for one in DECLARED_SHARED_TABLES
                if staged.has_staged(one.staged)
            },
        )

    def slot(self, item_id: int) -> _Slot | None:
        return self.slots.get(item_id)

    def table(self, named: SharedDropTable) -> SharedTable:
        found = self.tables.get(named)
        if found is None:
            raise UnreadableSlot(DECLARED.name, named.value)
        return found


class _Roll:
    def __init__(
        self,
        item_id: int,
        weight: float,
        low: int,
        high: int,
        rolled_on: SharedDropTable | None = None,
        denominator: float | None = None,
    ) -> None:
        self.item_id = item_id
        self.weight = weight
        self.low = low
        self.high = high
        self.rolled_on = rolled_on
        self.denominator = denominator

    def joined(self, other: _Roll) -> _Roll:
        return _Roll(
            self.item_id,
            self.weight + other.weight,
            min(self.low, other.low),
            max(self.high, other.high),
            self.rolled_on or other.rolled_on,
            _joined(self.denominator, other.denominator),
        )


def _joined(one: float | None, other: float | None) -> float | None:
    if one is None:
        return other
    if other is None:
        return one
    return one + other


def read_drops(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Turn every table row into a drop edge for every npc the table serves."""
    reserved = Reserved.of(staged)
    edges: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    folded = 0
    expanded = 0
    for table in staged.records(DECLARED):
        owners = _owners(table, known, skipped)
        clues: dict[EntityKey, ClueLevel] = {}
        for section in SECTIONS:
            read = _rolls(table, section, known, reserved, skipped)
            folded += read.folded
            expanded += read.expanded
            skipped.extend(read.dropped)
            for owner in owners:
                edges.extend(_edges(owner, table, section, read.rolls, read.total))
                if read.clue is not None:
                    clues.setdefault(owner, read.clue)
        entities.extend(_clue_patches(clues))
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, edges, entities),
        skipped=tuple(skipped),
        notes=(
            GUARANTEED_NOTE,
            SLOT_NOTE,
            f"{folded} rows folded into an earlier row for the same item",
            f"{expanded} rows read as a roll on a table many npcs share",
            f"{len(entities)} npcs told which treasure trail they drop by their table",
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


@dataclass(frozen=True)
class _Read:
    """One section of one table, once each reserved id is read as what it stands for."""

    rolls: tuple[_Roll, ...]
    total: float
    dropped: list[Skipped]
    folded: int
    expanded: int
    clue: ClueLevel | None


def _rolls(
    table: Mapping[str, Any],
    section: DropTableKind,
    known: frozenset[EntityKey],
    reserved: Reserved,
    skipped: list[Skipped],
) -> _Read:
    rows = table.get(section.value) or []
    dropped: list[Skipped] = []
    ordered: list[_Roll] = []
    at: dict[int, int] = {}
    folded = 0
    expanded = 0
    clue: ClueLevel | None = None
    total = sum(_weight(row, int(str(row[ID_FIELD]))) for row in rows)
    for row in rows:
        item_id = int(str(row[ID_FIELD]))
        weight = _weight(row, item_id)
        if weight <= 0:
            dropped.append(_skip(SkipReason.NO_CHANCE, item_id))
            continue
        slot = reserved.slot(item_id)
        if slot is not None:
            if slot.clue is not None:
                clue = _hardest(clue, slot.clue)
                dropped.append(_skip(SkipReason.RESERVED_SLOT, item_id))
                continue
            if slot.table is None:
                dropped.append(_skip(SkipReason.NO_DROP, item_id))
                continue
            widened = _widened(reserved, slot.table, weight, section, known)
            expanded += 1
            dropped.extend(widened.dropped)
            for one in widened.rolls:
                folded += _keep(ordered, at, one)
            continue
        item = EntityKey(type=EntityType.ITEM, id=item_id)
        if item not in known:
            dropped.append(_skip(SkipReason.UNKNOWN_TARGET, item_id))
            continue
        folded += _keep(
            ordered,
            at,
            _Roll(
                item_id,
                weight,
                _amount(row, item_id, MIN_FIELD),
                _amount(row, item_id, MAX_FIELD),
            ),
        )
    return _Read(tuple(ordered), total, dropped, folded, expanded, clue)


def _hardest(one: ClueLevel | None, other: ClueLevel) -> ClueLevel:
    if one is None:
        return other
    return max(one, other, key=lambda level: level.ordinal)


def _keep(ordered: list[_Roll], at: dict[int, int], roll: _Roll) -> int:
    seen = at.get(roll.item_id)
    if seen is None:
        at[roll.item_id] = len(ordered)
        ordered.append(roll)
        return 0
    ordered[seen] = ordered[seen].joined(roll)
    return 1


@dataclass(frozen=True)
class _Widened:
    """The rows one reserved roll stands for, in the units of the section holding it."""

    rolls: tuple[_Roll, ...]
    dropped: list[Skipped]


def _widened(
    reserved: Reserved,
    named: SharedDropTable,
    weight: float,
    section: DropTableKind,
    known: frozenset[EntityKey],
) -> _Widened:
    """Spread one roll on a shared table over the rows that table can give back."""
    shared = reserved.table(named)
    rolls: list[_Roll] = []
    dropped: list[Skipped] = []
    for row in shared.rows:
        if row.weight <= 0:
            continue
        if reserved.slot(row.id) is not None:
            dropped.append(_skip(SkipReason.NO_DROP, row.id))
            continue
        if EntityKey(type=EntityType.ITEM, id=row.id) not in known:
            dropped.append(_skip(SkipReason.UNKNOWN_TARGET, row.id))
            continue
        share = row.weight / shared.total
        certain = section is GUARANTEED
        rolls.append(
            _Roll(
                row.id,
                row.weight if certain else weight * share,
                max(row.min_amount, 1),
                max(row.max_amount, row.min_amount, 1),
                named,
                shared.total if certain else None,
            )
        )
    return _Widened(tuple(rolls), dropped)


def _skip(reason: SkipReason, item_id: int) -> Skipped:
    return Skipped(
        source=DECLARED.name,
        reason=reason,
        detail=str(EntityKey(type=EntityType.ITEM, id=item_id)),
    )


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


def _clue_patches(clues: Mapping[EntityKey, ClueLevel]) -> list[dict[str, Any]]:
    return [
        {
            "type": key.type.value,
            "id": key.id,
            "mode": "patch",
            "claims": False,
            "attributes": {"clue_level": level.value},
            "source_ref": f"{DECLARED.name}#{key.id}",
        }
        for key, level in sorted(clues.items(), key=lambda pair: pair[0].id)
    ]


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
                "rolled_on": roll.rolled_on.value if roll.rolled_on else None,
                "min_amount": roll.low,
                "max_amount": roll.high,
            },
        }
        for roll in rolls
    ]


def _denominator(roll: _Roll, section: DropTableKind, total: float) -> float:
    if roll.denominator is not None:
        return roll.denominator
    return roll.weight if section is GUARANTEED else total


def _document(
    staged: StagedSources,
    edges: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]],
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": DECLARED.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CONFIG.value,
                "source_file": DECLARED.name,
                "game_version": str(staged.game_version(DECLARED.staged)),
                "entities": list(entities),
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


CONSTANTS_SOURCE: Final = """
package org.rs09.consts

object Items {
    const val DWARF_REMAINS_0 = 0
    const val TOOLKIT_1 = 1
    const val TINDERBOX_31 = 31
    const val NULL_799 = 799
    const val ROTTEN_POTATO_5733 = 5733
    const val GRANITE_LOBSTER_POUCH_12070 = 12070
    const val SACRED_CLAY_POUCH_CLASS_1_14422 = 14422
    const val SACRED_CLAY_POUCH_CLASS_2_14424 = 14424
    const val SACRED_CLAY_POUCH_CLASS_3_14426 = 14426
    const val SACRED_CLAY_POUCH_CLASS_4_14428 = 14428
    const val SACRED_CLAY_POUCH_CLASS_5_14430 = 14430
}
"""

RARE_SOURCE: Final = """
<RDT>
    <item id="995" minAmt="30" maxAmt="30" weight="30"/>
    <item id="1149" minAmt="1" maxAmt="1" weight="10"/>
    <item id="0" minAmt="1" maxAmt="1" weight="60"/>
</RDT>
"""


def _sources(tmp_path: Any, tables: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    from wiki_api.pipeline.enums.constants import read_constants
    from wiki_api.pipeline.staging.shared import read_shared_table

    constants = read_constants(CONSTANTS_SOURCE, "Items", "Items.kt")
    rare = read_shared_table(RARE_SOURCE, "rare", "RDT.xml")
    return staged_from(
        tmp_path,
        {
            DECLARED.staged: json.dumps(tables),
            "constants/Items.json": constants.model_dump_json(),
            "shared/rare.json": rare.model_dump_json(),
        },
    )


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


def test_the_id_standing_for_no_drop_never_becomes_one(tmp_path: Any) -> None:
    table = {
        "ids": "50",
        "default": [],
        "charm": [],
        "main": [_row(995, "1.0"), _row(0, "4.0")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert [edge.dst.id for edge in outcome.read.document.edges] == [995]
    assert outcome.skipped_by_reason() == {"no_drop": 1}


def test_the_no_drop_row_still_counts_towards_what_a_roll_is_measured_against(
    tmp_path: Any,
) -> None:
    table = {
        "ids": "50",
        "default": [],
        "charm": [],
        "main": [_row(995, "1.0"), _row(0, "4.0")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    coins = outcome.read.document.edges[0]
    assert coins.attributes["denominator"] == 5.0


def test_a_roll_on_a_shared_table_becomes_the_items_that_table_gives(
    tmp_path: Any,
) -> None:
    table = {"ids": "50", "default": [], "charm": [], "main": [_row(31, "1.0")]}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert [edge.dst.id for edge in outcome.read.document.edges] == [995, 1149]
    coins = outcome.read.document.edges[0]
    assert coins.attributes["rolled_on"] == "rare"
    assert coins.attributes["weight"] == 0.3
    assert coins.attributes["min_amount"] == 30


def test_a_shared_table_roll_keeps_the_chance_the_two_tables_multiply_to(
    tmp_path: Any,
) -> None:
    table = {
        "ids": "50",
        "default": [],
        "charm": [],
        "main": [_row(31, "1.0"), _row(536, "3.0")],
    }
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    coins = next(one for one in outcome.read.document.edges if one.dst.id == 995)
    assert coins.attributes["denominator"] == 4.0
    assert coins.attributes["weight"] == 0.3


def test_a_treasure_trail_slot_tells_the_npc_which_trail_it_drops(
    tmp_path: Any,
) -> None:
    table = {"ids": "50", "default": [], "charm": [], "main": [_row(12070, "1.0")]}
    outcome = read_drops(_sources(tmp_path, [table]), _known())
    assert outcome.read.document.edges == ()
    patched = outcome.read.document.entities[0]
    assert patched.key == EntityKey(type=EntityType.NPC, id=50)
    assert patched.attributes == {"clue_level": "hard"}
    assert patched.claims is False


def test_a_reserved_id_the_constants_do_not_declare_stops_the_build(
    tmp_path: Any,
) -> None:
    import json

    import pytest
    from tests.sources import staged_from

    from wiki_api.pipeline.enums.constants import read_constants

    thin = read_constants(
        "package org.rs09.consts\n\nobject Items {\n    const val TOOLKIT_1 = 1\n}\n",
        "Items",
        "Items.kt",
    )
    staged = staged_from(
        tmp_path,
        {
            DECLARED.staged: json.dumps([]),
            "constants/Items.json": thin.model_dump_json(),
        },
    )
    with pytest.raises(UnreadableSlot):
        read_drops(staged, _known())
