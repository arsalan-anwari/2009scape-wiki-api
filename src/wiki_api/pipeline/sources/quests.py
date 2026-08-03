"""Read the staged quest table into quest entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredTable(enum="Quests", path="content/data/Quests.kt")
NAME_COLUMN: Final = "questName"
UNIMPLEMENTED_NOTE: Final = (
    "the enum names every quest and says nothing else about it, so nothing here "
    "carries a difficulty, a length or a reward yet"
)


def source_keys(staged: StagedSources) -> tuple[str, ...]:
    """The natural keys the quest table declares, in the order it declares them."""
    return tuple(constant.name for constant in staged.table(DECLARED).constants)


def read_quests(
    staged: StagedSources,
    allocation: IdentityAllocation,
    overridden: frozenset[EntityKey],
) -> SourceOutcome:
    """Turn every declared quest into an entity, numbered by the allocation file."""
    table = staged.table(DECLARED)
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for constant in table.constants:
        quest_id = allocation.id_of(constant.name)
        if quest_id is None:
            raise UnallocatedIdentity(EntityType.QUEST.value, constant.name)
        key = EntityKey(type=EntityType.QUEST, id=quest_id)
        if key in overridden:
            skipped.append(
                Skipped(
                    source=DECLARED.filename,
                    reason=SkipReason.OVERRIDDEN,
                    detail=str(key),
                )
            )
            continue
        entities.append(
            {
                "type": EntityType.QUEST.value,
                "id": quest_id,
                "name": _name(constant.values, constant.name),
                "source_key": constant.name,
                "source_ref": f"{DECLARED.filename}#{constant.name}",
                "attributes": {},
            }
        )
    return SourceOutcome(
        source=DECLARED.filename,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=(f"{len(table.constants)} declared", UNIMPLEMENTED_NOTE),
    )


def _name(values: Mapping[str, Any], constant: str) -> str:
    named = values.get(NAME_COLUMN)
    return named if isinstance(named, str) and named.strip() else constant


def _document(
    staged: StagedSources, entities: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": DECLARED.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CODE.value,
                "source_file": DECLARED.filename,
                "game_version": str(staged.game_version(DECLARED.staged)),
                "entities": list(entities),
            },
        }
    )


# test cases


def _sources(tmp_path: Any, constants: list[tuple[str, str]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    table = {
        "enum": "Quests",
        "source_file": "Quests.kt",
        "language": "kotlin",
        "columns": [NAME_COLUMN],
        "constants": [
            {"name": name, "values": {NAME_COLUMN: label}} for name, label in constants
        ],
    }
    return staged_from(tmp_path, {DECLARED.staged: json.dumps(table)})


def _allocation(**ids: int) -> IdentityAllocation:
    from wiki_api.pipeline.identity import IdentityAllocation

    return IdentityAllocation(type=EntityType.QUEST, ids=dict(ids))


def test_a_declared_quest_becomes_an_entity_keyed_by_its_constant(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        frozenset(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.id == 1
    assert entity.name == "Death Plateau"
    assert entity.source_key == "DEATH_PLATEAU"


def test_the_natural_keys_come_back_in_the_order_the_source_declares_them(
    tmp_path: Any,
) -> None:
    staged = _sources(tmp_path, [("B_QUEST", "B"), ("A_QUEST", "A")])
    assert source_keys(staged) == ("B_QUEST", "A_QUEST")


def test_a_quest_nobody_numbered_stops_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(UnallocatedIdentity) as caught:
        read_quests(
            _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
            _allocation(),
            frozenset(),
        )
    assert "DEATH_PLATEAU" in str(caught.value)


def test_a_quest_an_overlay_defines_is_left_to_the_overlay(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        frozenset({EntityKey(type=EntityType.QUEST, id=1)}),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"overridden": 1}


def test_a_quest_with_no_written_name_falls_back_to_its_constant(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "  ")]),
        _allocation(DEATH_PLATEAU=1),
        frozenset(),
    )
    assert outcome.read.document.entities[0].name == "DEATH_PLATEAU"


def test_the_document_says_the_fact_came_from_code(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        frozenset(),
    )
    assert outcome.read.document.source is SourceKind.GAME_CODE
