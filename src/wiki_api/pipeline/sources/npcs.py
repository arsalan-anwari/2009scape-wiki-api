"""Read the staged npc config into npc entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.attributes import NpcAttributes
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, attributes, text
from wiki_api.pipeline.sources.errors import ConflictingRecords
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredConfig(name="npc_configs.json")
ID_FIELD: Final = "id"
NAME_FIELD: Final = "name"
EXAMINE_FIELD: Final = "examine"
SPINE: Final = (ID_FIELD, NAME_FIELD, EXAMINE_FIELD)
LISTED: Final = ("combat_audio",)
IGNORED: Final[tuple[str, ...]] = ()


def read_npcs(staged: StagedSources, overridden: frozenset[EntityKey]) -> SourceOutcome:
    """Turn every staged npc record into an entity, minus the ones an overlay owns."""
    declared = set(NpcAttributes.model_fields)
    records = staged.records(DECLARED)
    seen: dict[int, str] = {}
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    unnamed = 0
    for record in records:
        identity = str(record[ID_FIELD])
        npc_id = int(identity)
        name = text(record.get(NAME_FIELD)) or ""
        key = EntityKey(type=EntityType.NPC, id=npc_id)
        first = seen.get(npc_id)
        if first is not None and key not in overridden:
            raise ConflictingRecords(DECLARED.name, str(key), first, name)
        seen[npc_id] = name
        if key in overridden:
            skipped.append(
                Skipped(
                    source=DECLARED.name, reason=SkipReason.OVERRIDDEN, detail=str(key)
                )
            )
            continue
        if not name:
            unnamed += 1
        entities.append(
            {
                "type": EntityType.NPC.value,
                "id": npc_id,
                "name": name,
                "description": text(record.get(EXAMINE_FIELD)),
                "source_ref": f"{DECLARED.name}#{npc_id}",
                "attributes": attributes(
                    record,
                    source=DECLARED.name,
                    identity=identity,
                    spine=SPINE,
                    ignored=IGNORED,
                    declared=declared,
                    listed=LISTED,
                ),
            }
        )
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{len(records)} records read",
            f"{unnamed} carry no name and are kept out of search",
        ),
    )


def _document(
    staged: StagedSources, entities: Sequence[Mapping[str, Any]]
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
            },
        }
    )


# test cases


def _sources(tmp_path: Any, records: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(tmp_path, {DECLARED.staged: json.dumps(records)})


def test_a_record_becomes_an_entity_with_its_combat_stats(tmp_path: Any) -> None:
    outcome = read_npcs(
        _sources(
            tmp_path,
            [
                {
                    "id": "1",
                    "name": "Man",
                    "examine": "One of many citizens.",
                    "lifepoints": "10",
                    "attack_level": "5",
                    "combat_audio": "511,513,512",
                    "safespot": None,
                }
            ],
        ),
        frozenset(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.name == "Man"
    assert entity.attributes["lifepoints"] == "10"
    assert entity.attributes["combat_audio"] == [511, 513, 512]
    assert "safespot" not in entity.attributes


def test_the_attributes_survive_the_model_that_declares_them(tmp_path: Any) -> None:
    outcome = read_npcs(
        _sources(tmp_path, [{"id": "50", "name": "KBD", "combat_style": "1"}]),
        frozenset(),
    )
    read = NpcAttributes.model_validate(outcome.read.document.entities[0].attributes)
    assert read.combat_style is not None


def test_an_npc_with_no_name_is_counted_and_carried(tmp_path: Any) -> None:
    outcome = read_npcs(
        _sources(tmp_path, [{"id": "1", "name": ""}, {"id": "2", "name": "Man"}]),
        frozenset(),
    )
    assert outcome.entities == 2
    assert any("1 carry no name" in note for note in outcome.notes)


def test_a_field_the_registry_does_not_declare_stops_the_build(tmp_path: Any) -> None:
    import pytest

    from wiki_api.pipeline.sources.errors import UnknownSourceField

    with pytest.raises(UnknownSourceField):
        read_npcs(
            _sources(tmp_path, [{"id": "1", "name": "X", "mood": "1"}]), frozenset()
        )


def test_two_records_for_one_id_stop_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(ConflictingRecords):
        read_npcs(
            _sources(tmp_path, [{"id": "1", "name": "A"}, {"id": "1", "name": "B"}]),
            frozenset(),
        )
