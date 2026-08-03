"""Read the staged ranged weapon config into what each weapon fires."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, numbers
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredConfig(name="ranged_weapon_configs.json")
ITEM_FIELD: Final = "itemId"
AMMUNITION_FIELD: Final = "ammunition"


def read_ammunition(
    staged: StagedSources, known: frozenset[EntityKey]
) -> SourceOutcome:
    """Turn every ammunition line into an edge from the weapon to what it fires."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    own = 0
    for record in staged.records(DECLARED):
        weapon_id = int(str(record[ITEM_FIELD]))
        weapon = EntityKey(type=EntityType.ITEM, id=weapon_id)
        if weapon not in known:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(weapon),
                )
            )
            continue
        taken: set[int] = set()
        for order, ammunition_id in enumerate(
            numbers(
                record.get(AMMUNITION_FIELD),
                DECLARED.name,
                str(weapon_id),
                AMMUNITION_FIELD,
            )
        ):
            ammunition = EntityKey(type=EntityType.ITEM, id=ammunition_id)
            if ammunition not in known or ammunition_id in taken:
                skipped.append(
                    Skipped(
                        source=DECLARED.name,
                        reason=(
                            SkipReason.ALREADY_STATED
                            if ammunition_id in taken
                            else SkipReason.UNKNOWN_TARGET
                        ),
                        detail=str(ammunition),
                    )
                )
                continue
            taken.add(ammunition_id)
            own += ammunition == weapon
            edges.append(
                {
                    "src": str(weapon),
                    "rel": RelationshipType.USES_AMMUNITION.value,
                    "dst": str(ammunition),
                    "order_key": order,
                    "source_ref": (f"{DECLARED.name}#{weapon_id}.{AMMUNITION_FIELD}"),
                    "attributes": {},
                }
            )
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, edges),
        skipped=tuple(skipped),
        notes=(f"{own} weapons are their own ammunition",),
    )


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


def _sources(tmp_path: Any, records: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(tmp_path, {DECLARED.staged: json.dumps(records)})


def _known() -> frozenset[EntityKey]:
    return frozenset(
        EntityKey(type=EntityType.ITEM, id=item) for item in (767, 732, 877, 878)
    )


def test_a_weapon_points_at_every_round_it_takes(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "767", "ammunition": "877,878"}]), _known()
    )
    edges = outcome.read.document.edges
    assert [edge.dst.id for edge in edges] == [877, 878]
    assert edges[0].rel is RelationshipType.USES_AMMUNITION


def test_a_thrown_weapon_is_its_own_ammunition(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "732", "ammunition": "732"}]), _known()
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == edge.dst
    assert any("1 weapons are their own" in note for note in outcome.notes)


def test_a_round_nothing_defines_is_dropped_and_counted(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "767", "ammunition": "877,4242"}]), _known()
    )
    assert outcome.edges == 1
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_a_weapon_nothing_defines_is_dropped_and_counted(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "4242", "ammunition": "877"}]), _known()
    )
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_a_round_listed_twice_is_taken_once(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "767", "ammunition": "877,878,877"}]), _known()
    )
    assert outcome.edges == 2
    assert outcome.skipped_by_reason() == {"already_stated": 1}


def test_a_weapon_that_names_no_ammunition_yields_nothing(tmp_path: Any) -> None:
    outcome = read_ammunition(
        _sources(tmp_path, [{"itemId": "767", "ammunition": ""}]), _known()
    )
    assert outcome.edges == 0
