"""Read the staged quest table into quest entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType, RequirementKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.sources.overridden import Overridden
from wiki_api.pipeline.staging.declared import QUEST_SCAN, DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.enums.calls import BaseCall
    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredTable(enum="Quests", path="content/data/Quests.kt")
NAME_COLUMN: Final = "questName"
POINTS_POSITION: Final = 3
MAX_POINTS: Final = 10
UNWRITTEN_NOTE: Final = (
    "difficulty and length are stated nowhere the game controls, so no quest carries "
    "one; the community wiki states them and does not survive checking"
)
#: The one skill the game's code spells differently from the published vocabulary.
SKILL_NAMES: Final = {"RANGE": "ranged"}


def source_keys(staged: StagedSources) -> tuple[str, ...]:
    """The natural keys the quest table declares, in the order it declares them."""
    return tuple(constant.name for constant in staged.table(DECLARED).constants)


def read_quests(
    staged: StagedSources,
    allocation: IdentityAllocation,
    overridden: Overridden,
) -> SourceOutcome:
    """Turn every declared quest into an entity, numbered by the allocation file."""
    table = staged.table(DECLARED)
    implemented = _implementations(staged)
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for constant in table.constants:
        quest_id = allocation.id_of(constant.name)
        if quest_id is None:
            raise UnallocatedIdentity(EntityType.QUEST.value, constant.name)
        key = EntityKey(type=EntityType.QUEST, id=quest_id)
        if key in overridden:
            named = _name(constant.values, constant.name)
            overridden.check(key, named, constant.values)
            skipped.append(
                Skipped(
                    source=DECLARED.filename,
                    reason=SkipReason.OVERRIDDEN,
                    detail=str(key),
                )
            )
            continue
        written = implemented.get(constant.name)
        entities.append(
            {
                "type": EntityType.QUEST.value,
                "id": quest_id,
                "name": _name(constant.values, constant.name),
                "source_key": constant.name,
                "source_ref": _reference(constant.name, written),
                "attributes": _attributes(written),
            }
        )
    return SourceOutcome(
        source=DECLARED.filename,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{len(table.constants)} declared, {len(implemented)} implemented",
            f"{sum(1 for one in entities if one['attributes'])} carry quest points",
            UNWRITTEN_NOTE,
        ),
    )


def _implementations(staged: StagedSources) -> dict[str, BaseCall]:
    """What each implementing class hands the quest base class, keyed by constant."""
    if not staged.has_staged(QUEST_SCAN.staged):
        return {}
    return {call.constant: call for call in staged.calls(QUEST_SCAN)}


def _attributes(written: BaseCall | None) -> dict[str, Any]:
    """The points a quest awards and the start gates it gives, both stated in code."""
    if written is None:
        return {}
    attributes: dict[str, Any] = {}
    points = written.number(POINTS_POSITION)
    if points is not None and 0 <= points <= MAX_POINTS:
        attributes["quest_points"] = points
    gates = written.requires
    if gates is None:
        return attributes
    if gates.skills:
        attributes["requirements"] = [
            {"skill": SKILL_NAMES.get(name, name.lower()), "level": level}
            for name, level in gates.skills.items()
        ]
    if gates.quest_points is not None:
        attributes["quest_points_needed"] = gates.quest_points
    return attributes


def read_quest_gates(
    staged: StagedSources,
    allocation: IdentityAllocation,
    known: frozenset[EntityKey],
) -> SourceOutcome:
    """Turn every quest a class asks you to finish first into a link between the two."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for call in _implementations(staged).values():
        quest_id = allocation.id_of(call.constant)
        if call.requires is None or quest_id is None:
            continue
        quest = EntityKey(type=EntityType.QUEST, id=quest_id)
        for order, constant in enumerate(call.requires.quests):
            wanted = allocation.id_of(constant)
            first = (
                None if wanted is None else EntityKey(type=EntityType.QUEST, id=wanted)
            )
            if first is None or first not in known or first == quest:
                skipped.append(
                    Skipped(
                        source=QUEST_SCAN.staged,
                        reason=SkipReason.UNKNOWN_TARGET,
                        detail=f"{quest} -> {constant}",
                    )
                )
                continue
            edges.append(
                {
                    "src": str(quest),
                    "rel": RelationshipType.REQUIRES.value,
                    "dst": str(first),
                    "order_key": order,
                    "source_ref": f"{QUEST_SCAN.staged}#{call.constant}",
                    "attributes": {"kind": RequirementKind.COMPLETED.value},
                }
            )
    return SourceOutcome(
        source=f"{DECLARED.filename} gates",
        read=_document(staged, edges=edges),
        skipped=tuple(skipped),
        notes=(f"{len(edges)} quests must be finished first",),
    )


def _reference(constant: str, written: BaseCall | None) -> str:
    if written is None:
        return f"{DECLARED.filename}#{constant}"
    return f"{QUEST_SCAN.staged}#{constant}"


def _name(values: Mapping[str, Any], constant: str) -> str:
    named = values.get(NAME_COLUMN)
    return named if isinstance(named, str) and named.strip() else constant


def _document(
    staged: StagedSources,
    entities: Sequence[Mapping[str, Any]] = (),
    edges: Sequence[Mapping[str, Any]] = (),
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
                "edges": list(edges),
            },
        }
    )


# test cases


def _sources(
    tmp_path: Any,
    constants: list[tuple[str, str]],
    calls: list[dict[str, Any]] | None = None,
) -> StagedSources:
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
    files = {DECLARED.staged: json.dumps(table)}
    if calls is not None:
        files[QUEST_SCAN.staged] = json.dumps(
            {
                "base": "Quest",
                "qualifier": "Quests",
                "root": "content",
                "calls": calls,
            }
        )
    return staged_from(tmp_path, files)


def _allocation(**ids: int) -> IdentityAllocation:
    from wiki_api.pipeline.identity import IdentityAllocation

    return IdentityAllocation(type=EntityType.QUEST, ids=dict(ids))


def test_a_declared_quest_becomes_an_entity_keyed_by_its_constant(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.id == 1
    assert entity.name == "Death Plateau"
    assert entity.source_key == "DEATH_PLATEAU"


def test_an_implemented_quest_carries_the_points_its_own_class_hands_over(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(
            tmp_path,
            [("DEATH_PLATEAU", "Death Plateau")],
            calls=[
                {
                    "constant": "DEATH_PLATEAU",
                    "numbers": [44, 43, 1, 314],
                    "path": "Server/src/main/content/DeathPlateau.kt",
                }
            ],
        ),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.attributes["quest_points"] == 1
    assert entity.source_ref is not None
    assert entity.source_ref.endswith("#DEATH_PLATEAU")


def test_a_quest_nothing_implements_carries_no_points(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("TEST_QUEST", "Test Quest")], calls=[]),
        _allocation(TEST_QUEST=1),
        Overridden.of(),
    )
    assert outcome.read.document.entities[0].attributes == {}


def test_a_number_no_quest_could_award_is_left_out(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(
            tmp_path,
            [("DEATH_PLATEAU", "Death Plateau")],
            calls=[
                {"constant": "DEATH_PLATEAU", "numbers": [44, 43, 314], "path": "x.kt"}
            ],
        ),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of(),
    )
    assert outcome.read.document.entities[0].attributes == {}


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
            Overridden.of(),
        )
    assert "DEATH_PLATEAU" in str(caught.value)


def test_a_quest_an_overlay_defines_is_left_to_the_overlay(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of({EntityKey(type=EntityType.QUEST, id=1)}),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"overridden": 1}


def test_a_quest_with_no_written_name_falls_back_to_its_constant(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "  ")]),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of(),
    )
    assert outcome.read.document.entities[0].name == "DEATH_PLATEAU"


def _gated(**gates: Any) -> dict[str, Any]:
    return {
        "constant": "DESERT_TREASURE",
        "numbers": [32, 31, 3],
        "path": "Server/src/main/content/DesertTreasure.kt",
        "requires": {"enforced": True, **gates},
    }


def _known(*ids: int) -> frozenset[EntityKey]:
    return frozenset(EntityKey(type=EntityType.QUEST, id=one) for one in ids)


def test_the_levels_a_class_asks_for_reach_the_quest_it_belongs_to(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure")],
            calls=[_gated(skills={"MAGIC": 50, "SLAYER": 10})],
        ),
        _allocation(DESERT_TREASURE=32),
        Overridden.of(),
    )
    assert outcome.read.document.entities[0].attributes["requirements"] == [
        {"skill": "magic", "level": 50},
        {"skill": "slayer", "level": 10},
    ]


def test_the_one_skill_the_code_spells_differently_reaches_us_spelt_ours(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure")],
            calls=[_gated(skills={"RANGE": 30})],
        ),
        _allocation(DESERT_TREASURE=32),
        Overridden.of(),
    )
    stated = outcome.read.document.entities[0].attributes["requirements"]
    assert stated == [{"skill": "ranged", "level": 30}]


def test_the_quest_points_a_class_asks_for_are_not_the_ones_it_awards(
    tmp_path: Any,
) -> None:
    outcome = read_quests(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure")],
            calls=[_gated(quest_points=43)],
        ),
        _allocation(DESERT_TREASURE=32),
        Overridden.of(),
    )
    attributes = outcome.read.document.entities[0].attributes
    assert attributes["quest_points"] == 3
    assert attributes["quest_points_needed"] == 43


def test_a_quest_asked_for_first_becomes_a_link_between_the_two(
    tmp_path: Any,
) -> None:
    outcome = read_quest_gates(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure"), ("LOST_CITY", "Lost City")],
            calls=[_gated(quests=["LOST_CITY"])],
        ),
        _allocation(DESERT_TREASURE=32, LOST_CITY=70),
        _known(32, 70),
    )
    edge = outcome.read.document.edges[0]
    assert str(edge.src) == "quest:32"
    assert str(edge.dst) == "quest:70"
    assert edge.attributes["kind"] == "completed"


def test_a_quest_asked_for_that_the_build_does_not_hold_is_counted(
    tmp_path: Any,
) -> None:
    outcome = read_quest_gates(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure")],
            calls=[_gated(quests=["LOST_CITY"])],
        ),
        _allocation(DESERT_TREASURE=32),
        _known(32),
    )
    assert outcome.read.document.edges == ()
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_a_class_stating_no_gates_writes_no_links(tmp_path: Any) -> None:
    outcome = read_quest_gates(
        _sources(
            tmp_path,
            [("DESERT_TREASURE", "Desert Treasure")],
            calls=[
                {
                    "constant": "DESERT_TREASURE",
                    "numbers": [32, 31, 3],
                    "path": "x.kt",
                }
            ],
        ),
        _allocation(DESERT_TREASURE=32),
        _known(32),
    )
    assert outcome.read.document.edges == ()


def test_the_document_says_the_fact_came_from_code(tmp_path: Any) -> None:
    outcome = read_quests(
        _sources(tmp_path, [("DEATH_PLATEAU", "Death Plateau")]),
        _allocation(DEATH_PLATEAU=1),
        Overridden.of(),
    )
    assert outcome.read.document.source is SourceKind.GAME_CODE
