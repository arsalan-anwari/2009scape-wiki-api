"""Read the staged item config into item entities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.attributes import ItemAttributes
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind, WeaponType
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import (
    Skipped,
    SkipReason,
    attributes,
    requirements,
    text,
)
from wiki_api.pipeline.sources.errors import ConflictingRecords, DriftedVocabulary
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.sources.overridden import Overridden
from wiki_api.pipeline.staging.declared import WEAPON_TYPES, DeclaredConfig

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
ZERO_IS_ABSENT: Final[tuple[str, ...]] = ("archery_ticket_price",)
RENAMED: Final[Mapping[str, str]] = {"weapon_interface": "weapon_type"}
WEAPON_NOTE: Final = (
    "weapon_interface is a position in the game's own list of weapon types, so a "
    "constant inserted upstream would move every weapon along one; the names are "
    "checked against that list before any of them is read"
)
IGNORED_NOTE: Final = (
    "shop_price is left out: nothing in the game reads it, and the number a shop "
    "charges is worked out from a value only the cache carries"
)
DEFAULTED_NOTE: Final = (
    "archery_ticket_price is written as 0 on all but a handful of records, so a zero "
    "here is the writer's default rather than a price the archery shop charges"
)


def check_weapon_types(staged: StagedSources) -> None:
    """Refuse a build whose weapon list no longer says what this build reads by
    position.
    """
    if not staged.has_staged(WEAPON_TYPES.staged):
        return
    found = [constant.name for constant in staged.table(WEAPON_TYPES).constants]
    expected = [member.name for member in WeaponType]
    if found != expected:
        raise DriftedVocabulary(WEAPON_TYPES.filename, expected, found)


def read_items(staged: StagedSources, overridden: Overridden) -> SourceOutcome:
    """Turn every staged item record into an entity, minus the ones an overlay owns."""
    check_weapon_types(staged)
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
            overridden.check(key, name, record)
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
            zero_is_absent=ZERO_IS_ABSENT,
            renamed=RENAMED,
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
        notes=(
            f"{len(records)} records read",
            IGNORED_NOTE,
            DEFAULTED_NOTE,
            WEAPON_NOTE,
        ),
    )


def _refuse_a_second_record(
    seen: dict[int, str], item_id: int, name: str, overridden: Overridden
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
        Overridden.of(),
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


def test_a_price_the_writer_left_at_zero_is_not_published_as_a_price(
    tmp_path: Any,
) -> None:
    outcome = read_items(
        _sources(
            tmp_path,
            [
                {"id": "4587", "name": "Dragon scimitar", "archery_ticket_price": "0"},
                {"id": "890", "name": "Mithril arrow", "archery_ticket_price": "70"},
            ],
        ),
        Overridden.of(),
    )
    written = {
        entity.id: entity.attributes for entity in outcome.read.document.entities
    }
    assert "archery_ticket_price" not in written[4587]
    assert written[890]["archery_ticket_price"] == "70"


def test_the_attributes_survive_the_model_that_declares_them(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "4587", "name": "X", "bonuses": "0," * 14 + "25"}]),
        Overridden.of(),
    )
    read = ItemAttributes.model_validate(outcome.read.document.entities[0].attributes)
    assert read.bonuses is not None
    assert read.bonuses.ranged_strength == 25


def test_a_position_in_the_weapon_list_becomes_the_name_it_stands_for(
    tmp_path: Any,
) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "4587", "name": "X", "weapon_interface": "6"}]),
        Overridden.of(),
    )
    read = ItemAttributes.model_validate(outcome.read.document.entities[0].attributes)
    assert read.weapon_type is WeaponType.SCIMITAR


def test_the_source_field_never_reaches_the_artifact_under_its_own_name(
    tmp_path: Any,
) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "4587", "name": "X", "weapon_interface": "6"}]),
        Overridden.of(),
    )
    written = outcome.read.document.entities[0].attributes
    assert "weapon_interface" not in written
    assert written["weapon_type"] == "6"


def _with_weapon_list(tmp_path: Any, names: list[str]) -> StagedSources:
    import json

    from tests.sources import staged_from

    table = {
        "enum": WEAPON_TYPES.enum,
        "source_file": WEAPON_TYPES.filename,
        "language": "java",
        "columns": ["interfaceId"],
        "constants": [{"name": name, "values": {"interfaceId": 1}} for name in names],
    }
    return staged_from(
        tmp_path,
        {
            DECLARED.staged: json.dumps([{"id": "1", "name": "X"}]),
            WEAPON_TYPES.staged: json.dumps(table),
        },
    )


def test_a_weapon_list_that_still_agrees_builds(tmp_path: Any) -> None:
    staged = _with_weapon_list(tmp_path, [member.name for member in WeaponType])
    assert read_items(staged, Overridden.of()).entities == 1


def test_a_weapon_list_that_moved_underneath_stops_the_build(tmp_path: Any) -> None:
    import pytest

    names = [member.name for member in WeaponType]
    staged = _with_weapon_list(tmp_path, ["SLING", *names])
    with pytest.raises(DriftedVocabulary):
        read_items(staged, Overridden.of())


def test_a_build_with_no_weapon_list_staged_reads_items_anyway(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "1", "name": "X"}]), Overridden.of()
    )
    assert outcome.entities == 1


def test_a_field_the_registry_does_not_declare_stops_the_build(tmp_path: Any) -> None:
    import pytest

    from wiki_api.pipeline.sources.errors import UnknownSourceField

    with pytest.raises(UnknownSourceField):
        read_items(
            _sources(tmp_path, [{"id": "1", "name": "X", "sparkle": "yes"}]),
            Overridden.of(),
        )


def test_two_records_for_one_id_stop_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(ConflictingRecords):
        read_items(
            _sources(
                tmp_path,
                [{"id": "14422", "name": "Scroll"}, {"id": "14422", "name": "Slot"}],
            ),
            Overridden.of(),
        )


def test_an_overlay_that_defines_the_entity_settles_the_conflict(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(
            tmp_path,
            [{"id": "14422", "name": "Scroll"}, {"id": "14422", "name": "Slot"}],
        ),
        Overridden.of({EntityKey(type=EntityType.ITEM, id=14422)}),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"overridden": 2}


def test_an_item_with_no_name_is_still_carried(tmp_path: Any) -> None:
    outcome = read_items(_sources(tmp_path, [{"id": "1", "name": ""}]), Overridden.of())
    assert outcome.read.document.entities[0].name == ""


def test_the_document_names_the_commit_it_was_read_from(tmp_path: Any) -> None:
    outcome = read_items(
        _sources(tmp_path, [{"id": "1", "name": "X"}]), Overridden.of()
    )
    assert outcome.read.document.game_version.repo == "2009scape"
    assert outcome.read.document.source_file == DECLARED.name
