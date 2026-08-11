"""Read the slayer tables into tasks, who hands them out, and what counts for one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from wiki_api.pipeline.enums.reader import EnumConstant
    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.sources.staged import StagedSources

TASKS: Final = DeclaredTable(
    enum="Tasks", path="content/global/skill/slayer/Tasks.java"
)
MASTERS: Final = DeclaredTable(
    enum="Master", path="content/global/skill/slayer/Master.java"
)
TASK_PREFIX: Final = "Tasks."
SYMBOL_KEY: Final = "symbol"
ARGUMENTS_KEY: Final = "arguments"
MAX_LEVEL: Final = 99
WORD_SEPARATOR: Final = "_"
FLAGS: Final[Mapping[str, str]] = {"undead": "undead", "dragon": "dragonfire"}


def task_keys(staged: StagedSources) -> tuple[str, ...]:
    """The natural keys the slayer table declares, in the order it declares them."""
    if not staged.has_staged(TASKS.staged):
        return ()
    return tuple(constant.name for constant in staged.table(TASKS).constants)


def read_tasks(staged: StagedSources, allocation: IdentityAllocation) -> SourceOutcome:
    """Turn every declared assignment into an entity, numbered by the allocation."""
    constants = _constants(staged, TASKS)
    entities = []
    for constant in constants:
        task_id = allocation.id_of(constant.name)
        if task_id is None:
            raise UnallocatedIdentity(EntityType.TASK.value, constant.name)
        entities.append(
            {
                "type": EntityType.TASK.value,
                "id": task_id,
                "name": _readable(constant.name),
                "source_key": constant.name,
                "source_ref": f"{TASKS.filename}#{constant.name}",
                "attributes": _attributes(constant),
            }
        )
    return SourceOutcome(
        source=TASKS.filename,
        read=_document(staged, TASKS, entities=entities),
        notes=(f"{len(constants)} assignments declared",),
    )


def read_slayer_edges(
    staged: StagedSources, known: frozenset[EntityKey], tasks: Mapping[str, EntityKey]
) -> SourceOutcome:
    """Link each master to what it hands out, and each task to what counts for it."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for constant in _constants(staged, MASTERS):
        for edge in _assignments(constant, tasks):
            _keep(MASTERS, edge, edges, skipped, known, tasks)
    for constant in _constants(staged, TASKS):
        for edge in _monsters(constant, tasks):
            _keep(TASKS, edge, edges, skipped, known, tasks)
    return SourceOutcome(
        source=MASTERS.filename,
        read=_document(staged, MASTERS, edges=edges),
        skipped=tuple(skipped),
        notes=(f"{len(edges)} links written",),
    )


def _assignments(
    constant: EnumConstant, tasks: Mapping[str, EntityKey]
) -> Iterator[dict[str, Any]]:
    master = _whole(constant.values.get("npc_id"))
    if master is None:
        return
    fallback = _numbers(constant.values.get("default_assignment_range"))
    for handed in _listed(constant.values.get("tasks")):
        arguments = handed.get(ARGUMENTS_KEY) if isinstance(handed, dict) else None
        if not isinstance(arguments, list) or len(arguments) < 2:
            continue
        name = _task_named(arguments[0])
        weight = _whole(arguments[1])
        if name is None or weight is None or weight < 1:
            continue
        target = tasks.get(name)
        if target is None:
            continue
        least, most = _range(arguments[2] if len(arguments) > 2 else None, fallback)
        yield {
            "src": str(EntityKey(type=EntityType.NPC, id=master)),
            "rel": RelationshipType.ASSIGNS.value,
            "dst": str(target),
            "attributes": {
                "weight": weight,
                "min_amount": least,
                "max_amount": most,
            },
            "order_key": weight,
            "source_ref": f"{MASTERS.filename}#{constant.name}",
        }


def _monsters(
    constant: EnumConstant, tasks: Mapping[str, EntityKey]
) -> Iterator[dict[str, Any]]:
    target = tasks.get(constant.name)
    if target is None:
        return
    for npc_id in _numbers(constant.values.get("ids")):
        yield {
            "src": str(target),
            "rel": RelationshipType.SATISFIED_BY.value,
            "dst": str(EntityKey(type=EntityType.NPC, id=npc_id)),
            "attributes": {},
            "source_ref": f"{TASKS.filename}#{constant.name}",
        }


def _keep(
    declared: DeclaredTable,
    edge: dict[str, Any],
    edges: list[dict[str, Any]],
    skipped: list[Skipped],
    known: frozenset[EntityKey],
    tasks: Mapping[str, EntityKey],
) -> None:
    minted = set(tasks.values())
    seen = {(one["src"], one["dst"]) for one in edges}
    identity = (edge["src"], edge["dst"])
    missing = [
        endpoint
        for endpoint in identity
        if EntityKey.parse(endpoint) not in known
        and EntityKey.parse(endpoint) not in minted
    ]
    if missing:
        skipped.append(
            Skipped(
                source=declared.filename,
                reason=SkipReason.UNKNOWN_TARGET,
                detail=missing[0],
            )
        )
        return
    if identity in seen:
        skipped.append(
            Skipped(
                source=declared.filename,
                reason=SkipReason.ALREADY_STATED,
                detail=f"{identity[0]} {identity[1]}",
            )
        )
        return
    edges.append(edge)


def _attributes(constant: EnumConstant) -> dict[str, Any]:
    values = constant.values
    kept: dict[str, Any] = {}
    level = _whole(values.get("levelReq"))
    if level is not None and 1 <= level <= MAX_LEVEL:
        kept["slayer_level"] = level
    combat = _whole(values.get("combatCheck"))
    if combat is not None and combat >= 1:
        kept["combat_level"] = combat
    advice = [line for line in _listed(values.get("info")) if isinstance(line, str)]
    if advice:
        kept["advice"] = advice
    for column, declared in FLAGS.items():
        if isinstance(values.get(column), bool):
            kept[declared] = values[column]
    return kept


def _readable(constant: str) -> str:
    """Turn a screaming constant into the name a player would say."""
    words = constant.split(WORD_SEPARATOR)
    return " ".join([words[0].capitalize(), *(word.lower() for word in words[1:])])


def _constants(
    staged: StagedSources, declared: DeclaredTable
) -> tuple[EnumConstant, ...]:
    if not staged.has_staged(declared.staged):
        return ()
    return staged.table(declared).constants


def _task_named(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    symbol = value.get(SYMBOL_KEY)
    if not isinstance(symbol, str) or not symbol.startswith(TASK_PREFIX):
        return None
    return symbol.removeprefix(TASK_PREFIX)


def _range(stated: Any, fallback: tuple[int, ...]) -> tuple[int | None, int | None]:
    read = _numbers(stated) or fallback
    if len(read) != 2 or read[0] < 1 or read[1] < read[0]:
        return None, None
    return read[0], read[1]


def _listed(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value) if isinstance(value, list) else (value,)


def _numbers(value: Any) -> tuple[int, ...]:
    read = (_whole(one) for one in _listed(value))
    return tuple(number for number in read if number is not None)


def _whole(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def _document(
    staged: StagedSources,
    declared: DeclaredTable,
    entities: Sequence[Mapping[str, Any]] = (),
    edges: Sequence[Mapping[str, Any]] = (),
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": declared.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CODE.value,
                "source_file": declared.filename,
                "game_version": str(staged.version_of(declared.staged)),
                "entities": list(entities),
                "edges": list(edges),
            },
        }
    )


# test cases


def _table(declared: DeclaredTable, constants: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(
        {
            "enum": declared.enum,
            "source_file": declared.filename,
            "language": "java",
            "columns": [],
            "constants": constants,
        }
    )


def _staged(
    tmp_path: Any,
    tasks: list[dict[str, Any]] | None = None,
    masters: list[dict[str, Any]] | None = None,
) -> StagedSources:
    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {
            TASKS.staged: _table(TASKS, tasks or []),
            MASTERS.staged: _table(MASTERS, masters or []),
        },
    )


def _allocation(**ids: int) -> IdentityAllocation:
    from wiki_api.pipeline.identity import IdentityAllocation

    return IdentityAllocation(type=EntityType.TASK, ids=dict(ids))


BANSHEE: Final = {
    "name": "BANSHEE",
    "values": {
        "combatCheck": 20,
        "ids": [1612],
        "info": ["Banshees use a piercing scream."],
        "levelReq": 15,
        "undead": True,
        "dragon": False,
    },
}

TURAEL: Final = {
    "name": "TURAEL",
    "values": {
        "npc_id": 8273,
        "required_combat": 3,
        "required_slayer": 0,
        "default_assignment_range": [15, 50],
        "streakPoints": [0, 0, 0],
        "tasks": [{"call": "Task", "arguments": [{"symbol": "Tasks.BANSHEE"}, 8]}],
    },
}


def test_a_declared_assignment_becomes_an_entity_with_its_levels(
    tmp_path: Any,
) -> None:
    outcome = read_tasks(_staged(tmp_path, tasks=[BANSHEE]), _allocation(BANSHEE=1))
    entity = outcome.read.document.entities[0]
    assert entity.name == "Banshee"
    assert entity.source_key == "BANSHEE"
    assert entity.attributes["slayer_level"] == 15
    assert entity.attributes["combat_level"] == 20
    assert entity.attributes["undead"] is True
    assert entity.attributes["dragonfire"] is False


def test_a_task_nobody_numbered_stops_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(UnallocatedIdentity) as caught:
        read_tasks(_staged(tmp_path, tasks=[BANSHEE]), _allocation())
    assert "BANSHEE" in str(caught.value)


def test_a_master_hands_out_a_task_with_the_weight_it_declares(tmp_path: Any) -> None:
    task = EntityKey(type=EntityType.TASK, id=1)
    outcome = read_slayer_edges(
        _staged(tmp_path, tasks=[BANSHEE], masters=[TURAEL]),
        frozenset({EntityKey(type=EntityType.NPC, id=8273)}),
        {"BANSHEE": task},
    )
    assigned = [
        edge
        for edge in outcome.read.document.edges
        if edge.rel is RelationshipType.ASSIGNS
    ]
    assert len(assigned) == 1
    assert assigned[0].dst == task
    assert assigned[0].attributes["weight"] == 8
    assert assigned[0].attributes["min_amount"] == 15
    assert assigned[0].attributes["max_amount"] == 50


def test_a_task_names_the_monsters_that_count_towards_it(tmp_path: Any) -> None:
    task = EntityKey(type=EntityType.TASK, id=1)
    outcome = read_slayer_edges(
        _staged(tmp_path, tasks=[BANSHEE]),
        frozenset({EntityKey(type=EntityType.NPC, id=1612)}),
        {"BANSHEE": task},
    )
    satisfied = [
        edge
        for edge in outcome.read.document.edges
        if edge.rel is RelationshipType.SATISFIED_BY
    ]
    assert [edge.dst.id for edge in satisfied] == [1612]


def test_a_monster_no_source_declares_is_counted_rather_than_written(
    tmp_path: Any,
) -> None:
    outcome = read_slayer_edges(
        _staged(tmp_path, tasks=[BANSHEE]),
        frozenset(),
        {"BANSHEE": EntityKey(type=EntityType.TASK, id=1)},
    )
    assert outcome.read.document.edges == ()
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_a_constant_reads_as_the_name_a_player_would_say() -> None:
    assert _readable("ABERRANT_SPECTRES") == "Aberrant spectres"
    assert _readable("ANKOU") == "Ankou"


def test_a_master_whose_task_nobody_declares_writes_nothing(tmp_path: Any) -> None:
    outcome = read_slayer_edges(
        _staged(tmp_path, masters=[TURAEL]),
        frozenset({EntityKey(type=EntityType.NPC, id=8273)}),
        {},
    )
    assert outcome.read.document.edges == ()
