"""Turn the staged cache decode into the facts the declared sources cannot carry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.entity import VariantKind
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import (
    OverlayMode,
    OverlayPrecedence,
    OverlaySource,
)
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.journal import QUEST_LIST, read_journal
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import (
    DATAMAP_EXTRACT,
    ITEM_EXTRACT,
    NPC_EXTRACT,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

ID_FIELD: Final = "id"
VALUE_FIELD: Final = "value"
BASE_VALUE_ATTRIBUTE: Final = "base_value"
NOTE_ID_FIELD: Final = "note_id"
NOTE_TEMPLATE_FIELD: Final = "note_template_id"
LEND_ID_FIELD: Final = "lend_id"
LEND_TEMPLATE_FIELD: Final = "lend_template_id"
COMBAT_LEVEL_FIELD: Final = "combat_level"
MEMBERS_ATTRIBUTE: Final = "members"
HIGH_ALCHEMY_RATE: Final = 0.6
LOW_ALCHEMY_RATE: Final = 0.4
UNSTAGED_VERSION: Final = "2009scape@unknown"


def alchemy_value(value: int, rate: float) -> int:
    """What alchemy pays for an item, rounded the way the game rounds it."""
    scaled = value * rate
    floor = int(scaled // 1)
    remainder = scaled - floor
    if remainder > 0.5:
        return floor + 1
    if remainder < 0.5:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def read_cache_items(
    staged: StagedSources, known: frozenset[EntityKey]
) -> SourceOutcome:
    """Patch every item the cache prices or marks as a copy of another item."""
    records = staged.extract(ITEM_EXTRACT) if staged.has_extract(ITEM_EXTRACT) else ()
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    variants = 0
    priced = 0
    for record in records:
        item_id = int(record[ID_FIELD])
        key = EntityKey(type=EntityType.ITEM, id=item_id)
        if key not in known:
            skipped.append(
                Skipped(
                    source=ITEM_EXTRACT.staged,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(key),
                )
            )
            continue
        patch = _item_patch(record, known)
        if _copy_of(record)[0] is not None and (
            patch is None or "canonical_id" not in patch
        ):
            skipped.append(
                Skipped(
                    source=ITEM_EXTRACT.staged,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(key),
                )
            )
        if patch is None:
            continue
        if BASE_VALUE_ATTRIBUTE in patch.get("attributes", {}):
            priced += 1
        if patch.get("variant_kind") is not None:
            variants += 1
        entities.append({"type": EntityType.ITEM.value, "id": item_id, **patch})
    return SourceOutcome(
        source=ITEM_EXTRACT.staged,
        read=_document(staged, ITEM_EXTRACT.staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{len(records)} definitions read",
            f"{priced} priced, {variants} collapsed onto the item they copy",
            _revision_note(staged, ITEM_EXTRACT.staged),
        ),
    )


def read_cache_npcs(
    staged: StagedSources, known: frozenset[EntityKey]
) -> SourceOutcome:
    """Patch every npc the cache gives a combat level."""
    records = staged.extract(NPC_EXTRACT) if staged.has_extract(NPC_EXTRACT) else ()
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in records:
        level = record.get(COMBAT_LEVEL_FIELD)
        if level is None:
            continue
        npc_id = int(record[ID_FIELD])
        key = EntityKey(type=EntityType.NPC, id=npc_id)
        if key not in known:
            skipped.append(
                Skipped(
                    source=NPC_EXTRACT.staged,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(key),
                )
            )
            continue
        entities.append(
            {
                "type": EntityType.NPC.value,
                "id": npc_id,
                "mode": OverlayMode.PATCH.value,
                "attributes": {COMBAT_LEVEL_FIELD: int(level)},
                "source_ref": f"{NPC_EXTRACT.staged}#{npc_id}",
            }
        )
    return SourceOutcome(
        source=NPC_EXTRACT.staged,
        read=_document(staged, NPC_EXTRACT.staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{len(records)} definitions read",
            f"{len(entities)} carry a combat level",
            _revision_note(staged, NPC_EXTRACT.staged),
        ),
    )


def read_cache_quests(
    staged: StagedSources, named: Mapping[str, EntityKey]
) -> SourceOutcome:
    """Patch every quest the journal's own list puts on one side of the members line."""
    journal = read_journal(staged)
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for name, key in sorted(named.items(), key=lambda pair: pair[1].id):
        members = journal.members_only(name)
        if members is None:
            skipped.append(
                Skipped(
                    source=DATAMAP_EXTRACT.staged,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=name,
                )
            )
            continue
        entities.append(
            {
                "type": EntityType.QUEST.value,
                "id": key.id,
                "mode": OverlayMode.PATCH.value,
                "attributes": {MEMBERS_ATTRIBUTE: members},
                "source_ref": f"{DATAMAP_EXTRACT.staged}#{QUEST_LIST}",
            }
        )
    return SourceOutcome(
        source=DATAMAP_EXTRACT.staged,
        read=_document(staged, DATAMAP_EXTRACT.staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{len(journal.listed)} quests listed in the journal",
            f"{len(entities)} matched a declared quest, {len(skipped)} did not",
            _revision_note(staged, DATAMAP_EXTRACT.staged),
        ),
    )


def item_values(staged: StagedSources) -> Mapping[int, int]:
    """What each item is worth, which is what every shop price is worked out from."""
    if not staged.has_extract(ITEM_EXTRACT):
        return {}
    return {
        int(record[ID_FIELD]): int(record[VALUE_FIELD])
        for record in staged.extract(ITEM_EXTRACT)
        if record.get(VALUE_FIELD)
    }


def _item_patch(
    record: Mapping[str, Any], known: frozenset[EntityKey]
) -> dict[str, Any] | None:
    attributes: dict[str, Any] = {}
    value = record.get(VALUE_FIELD)
    if value:
        attributes[BASE_VALUE_ATTRIBUTE] = int(value)
        attributes["high_alch_value"] = alchemy_value(int(value), HIGH_ALCHEMY_RATE)
        attributes["low_alch_value"] = alchemy_value(int(value), LOW_ALCHEMY_RATE)
    canonical, kind = _copy_of(record)
    if canonical is not None:
        copied = EntityKey(type=EntityType.ITEM, id=canonical)
        if copied not in known:
            canonical, kind = None, None
    if not attributes and canonical is None:
        return None
    patch: dict[str, Any] = {
        "mode": OverlayMode.PATCH.value,
        "source_ref": f"{ITEM_EXTRACT.staged}#{record[ID_FIELD]}",
    }
    if attributes:
        patch["attributes"] = attributes
    if canonical is not None and kind is not None:
        patch["canonical_id"] = canonical
        patch["variant_kind"] = kind.value
        patch["searchable"] = False
    return patch


def _copy_of(record: Mapping[str, Any]) -> tuple[int | None, VariantKind | None]:
    if (
        record.get(NOTE_TEMPLATE_FIELD) is not None
        and record.get(NOTE_ID_FIELD) is not None
    ):
        return int(record[NOTE_ID_FIELD]), VariantKind.NOTED
    if (
        record.get(LEND_TEMPLATE_FIELD) is not None
        and record.get(LEND_ID_FIELD) is not None
    ):
        return int(record[LEND_ID_FIELD]), VariantKind.BOUND
    return None, None


def _revision_note(staged: StagedSources, path: str) -> str:
    revision = _staged_revision(staged, path)
    return f"decoded from {revision}" if revision else "no revision recorded"


def _staged_revision(staged: StagedSources, path: str) -> str | None:
    for entry in staged.manifest.files:
        if entry.path == path:
            return entry.source_revision
    return None


def _game_version(staged: StagedSources, path: str) -> str:
    for entry in staged.manifest.files:
        if entry.path == path:
            return str(entry.game_version)
    versions = sorted({str(entry.game_version) for entry in staged.manifest.files})
    return versions[0] if versions else UNSTAGED_VERSION


def _document(
    staged: StagedSources, path: str, entities: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": path,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CACHE.value,
                "source_file": path,
                "source_revision": _staged_revision(staged, path),
                "game_version": _game_version(staged, path),
                "precedence": OverlayPrecedence.DECODED,
                "entities": list(entities),
            },
        }
    )


# test cases


def _staged(
    tmp_path: Any, records: list[dict[str, Any]], declared: Any = ITEM_EXTRACT
) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {declared.staged: json.dumps(records)},
        revisions={declared.staged: "index 19 revision 214"},
    )


def _items(*ids: int) -> frozenset[EntityKey]:
    return frozenset(EntityKey(type=EntityType.ITEM, id=item_id) for item_id in ids)


def test_alchemy_rounds_the_way_the_game_rounds_it() -> None:
    assert alchemy_value(160, HIGH_ALCHEMY_RATE) == 96
    assert alchemy_value(160, LOW_ALCHEMY_RATE) == 64
    assert alchemy_value(100000, HIGH_ALCHEMY_RATE) == 60000
    assert alchemy_value(5, HIGH_ALCHEMY_RATE) == 3
    assert alchemy_value(5, LOW_ALCHEMY_RATE) == 2


def test_an_item_is_patched_with_its_value_and_both_alchemy_prices(
    tmp_path: Any,
) -> None:
    outcome = read_cache_items(
        _staged(tmp_path, [{"id": 1050, "value": 160}]), _items(1050)
    )
    entity = outcome.read.document.entities[0]
    assert entity.mode is OverlayMode.PATCH
    assert entity.attributes["base_value"] == 160
    assert entity.attributes["high_alch_value"] == 96
    assert entity.attributes["low_alch_value"] == 64


def test_a_noted_item_collapses_onto_the_item_it_copies(tmp_path: Any) -> None:
    outcome = read_cache_items(
        _staged(
            tmp_path,
            [{"id": 4588, "note_id": 4587, "note_template_id": 799}],
        ),
        _items(4587, 4588),
    )
    entity = outcome.read.document.entities[0]
    assert entity.canonical_id == 4587
    assert entity.variant_kind is VariantKind.NOTED
    assert entity.searchable is False


def test_an_item_holding_a_note_id_but_no_template_stays_a_real_item(
    tmp_path: Any,
) -> None:
    outcome = read_cache_items(
        _staged(tmp_path, [{"id": 4587, "value": 1, "note_id": 4588}]), _items(4587)
    )
    entity = outcome.read.document.entities[0]
    assert entity.canonical_id is None
    assert entity.searchable is None


def test_a_lent_copy_collapses_onto_the_item_it_copies(tmp_path: Any) -> None:
    outcome = read_cache_items(
        _staged(tmp_path, [{"id": 13477, "lend_id": 4587, "lend_template_id": 13476}]),
        _items(4587, 13477),
    )
    entity = outcome.read.document.entities[0]
    assert entity.canonical_id == 4587
    assert entity.variant_kind is VariantKind.BOUND


def test_a_copy_of_an_item_nothing_declares_is_left_standing(tmp_path: Any) -> None:
    outcome = read_cache_items(
        _staged(
            tmp_path,
            [{"id": 4588, "value": 5, "note_id": 4587, "note_template_id": 799}],
        ),
        _items(4588),
    )
    entity = outcome.read.document.entities[0]
    assert entity.canonical_id is None
    assert entity.searchable is None
    assert entity.attributes["base_value"] == 5
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_a_definition_for_an_item_no_config_declares_is_counted(tmp_path: Any) -> None:
    outcome = read_cache_items(
        _staged(tmp_path, [{"id": 14000, "value": 5}]), _items(4587)
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_an_item_the_cache_says_nothing_useful_about_is_left_alone(
    tmp_path: Any,
) -> None:
    outcome = read_cache_items(_staged(tmp_path, [{"id": 4587}]), _items(4587))
    assert outcome.entities == 0
    assert outcome.skipped == ()


def test_the_document_says_which_revision_it_was_decoded_from(tmp_path: Any) -> None:
    outcome = read_cache_items(
        _staged(tmp_path, [{"id": 1050, "value": 160}]), _items(1050)
    )
    assert outcome.read.document.source is SourceKind.GAME_CACHE
    assert outcome.read.document.source_revision == "index 19 revision 214"
    assert any("revision 214" in note for note in outcome.notes)


def test_the_values_come_back_for_the_shops_to_price_from(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [{"id": 1050, "value": 160}, {"id": 4587}])
    assert item_values(staged) == {1050: 160}


def test_a_build_with_no_staged_cache_reads_nothing(tmp_path: Any) -> None:
    from tests.sources import staged_from

    staged = staged_from(tmp_path, {"configs/item_configs.json": "[]"})
    assert read_cache_items(staged, frozenset()).entities == 0
    assert item_values(staged) == {}


def test_an_npc_is_patched_with_the_level_the_cache_carries(tmp_path: Any) -> None:
    outcome = read_cache_npcs(
        _staged(tmp_path, [{"id": 50, "combat_level": 276}], NPC_EXTRACT),
        frozenset({EntityKey(type=EntityType.NPC, id=50)}),
    )
    entity = outcome.read.document.entities[0]
    assert entity.attributes["combat_level"] == 276
    assert entity.mode is OverlayMode.PATCH


def test_an_npc_with_no_level_in_the_cache_is_left_alone(tmp_path: Any) -> None:
    outcome = read_cache_npcs(
        _staged(tmp_path, [{"id": 0, "combat_level": None}], NPC_EXTRACT),
        frozenset({EntityKey(type=EntityType.NPC, id=0)}),
    )
    assert outcome.entities == 0
