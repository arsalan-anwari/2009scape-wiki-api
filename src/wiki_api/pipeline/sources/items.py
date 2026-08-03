"""Read the staged item config into item entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.attributes import ItemAttributes
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import (
    Skipped,
    SkipReason,
    attributes,
    requirements,
    text,
)
from wiki_api.pipeline.sources.errors import ConflictingRecords
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredConfig(name="item_configs.json")
ID_FIELD: Final = "id"
NAME_FIELD: Final = "name"
EXAMINE_FIELD: Final = "examine"
REQUIREMENTS_FIELD: Final = "requirements"
SPINE: Final = (ID_FIELD, NAME_FIELD, EXAMINE_FIELD)
LISTED: Final = ("attack_anims", "attack_audios")
IGNORED: Final[tuple[str, ...]] = ("durability", "shop_price")
IGNORED_NOTE: Final = (
    "shop_price is left out: nothing in the game reads it, and the number a shop "
    "charges is worked out from a value only the cache carries"
)


def read_items(
    staged: StagedSources, overridden: frozenset[EntityKey]
) -> SourceOutcome:
    """Turn every staged item record into an entity, minus the ones an overlay owns."""
    declared = set(ItemAttributes.model_fields)
    records = staged.records(DECLARED)
    seen: dict[int, str] = {}
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in records:
        identity = str(record[ID_FIELD])
        item_id = int(identity)
        name = text(record.get(NAME_FIELD)) or ""
        _refuse_a_second_record(seen, item_id, name, overridden)
        key = EntityKey(type=EntityType.ITEM, id=item_id)
        if key in overridden:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.OVERRIDDEN,
                    detail=str(key),
                )
            )
            continue
        kept = attributes(
            record,
            source=DECLARED.name,
            identity=identity,
            spine=SPINE,
            ignored=IGNORED,
            declared=declared,
            listed=LISTED,
        )
        if REQUIREMENTS_FIELD in kept:
            kept[REQUIREMENTS_FIELD] = requirements(
                record[REQUIREMENTS_FIELD], DECLARED.name, identity
            )
        entities.append(
            {
                "type": EntityType.ITEM.value,
                "id": item_id,
                "name": name,
                "description": text(record.get(EXAMINE_FIELD)),
                "source_ref": f"{DECLARED.name}#{item_id}",
                "attributes": kept,
            }
        )
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=(f"{len(records)} records read", IGNORED_NOTE),
    )


def _refuse_a_second_record(
    seen: dict[int, str], item_id: int, name: str, overridden: frozenset[EntityKey]
) -> None:
    first = seen.get(item_id)
    key = EntityKey(type=EntityType.ITEM, id=item_id)
    if first is not None and key not in overridden:
        raise ConflictingRecords(DECLARED.name, str(key), first, name)
    seen[item_id] = name


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


def test_a_record_becomes_an_entity_with_its_attributes(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(
            tmp_path,
            [
                {
                    "id": "4587",
                    "name": "Dragon scimitar",
                    "examine": "A vicious, curved sword.",
                    "weight": "1.8",
                    "tradeable": "true",
                    "requirements": "{0,60}",
                    "attack_anims": "390,381",
                    "durability": None,
                    "shop_price": "100000",
                }
            ],
        ),
        frozenset(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.id == 4587
    assert entity.name == "Dragon scimitar"
    assert entity.description == "A vicious, curved sword."
    assert entity.attributes["weight"] == "1.8"
    assert entity.attributes["requirements"] == ({"skill": 0, "level": 60},)
    assert entity.attributes["attack_anims"] == [390, 381]
    assert "shop_price" not in entity.attributes
    assert "durability" not in entity.attributes


def test_the_attributes_survive_the_model_that_declares_them(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "4587", "name": "X", "bonuses": "0," * 14 + "25"}]),
        frozenset(),
    )
    read = ItemAttributes.model_validate(outcome.read.document.entities[0].attributes)
    assert read.bonuses is not None
    assert read.bonuses.ranged_strength == 25


def test_a_field_the_registry_does_not_declare_stops_the_build(tmp_path: Any) -> None:
    import pytest

    from wiki_api.pipeline.sources.errors import UnknownSourceField

    with pytest.raises(UnknownSourceField):
        read_items(
            _sources(tmp_path, [{"id": "1", "name": "X", "sparkle": "yes"}]),
            frozenset(),
        )


def test_two_records_for_one_id_stop_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(ConflictingRecords):
        read_items(
            _sources(
                tmp_path,
                [{"id": "14422", "name": "Scroll"}, {"id": "14422", "name": "Slot"}],
            ),
            frozenset(),
        )


def test_an_overlay_that_defines_the_entity_settles_the_conflict(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(
            tmp_path,
            [{"id": "14422", "name": "Scroll"}, {"id": "14422", "name": "Slot"}],
        ),
        frozenset({EntityKey(type=EntityType.ITEM, id=14422)}),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"overridden": 2}


def test_an_item_with_no_name_is_still_carried(tmp_path: Any) -> None:
    outcome = read_items(_sources(tmp_path, [{"id": "1", "name": ""}]), frozenset())
    assert outcome.read.document.entities[0].name == ""


def test_the_document_names_the_commit_it_was_read_from(tmp_path: Any) -> None:
    outcome = read_items(_sources(tmp_path, [{"id": "1", "name": "X"}]), frozenset())
    assert outcome.read.document.game_version.repo == "2009scape"
    assert outcome.read.document.source_file == DECLARED.name
