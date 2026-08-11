from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.sources import staged_from
from wiki_api.core.results import Direction, Found
from wiki_api.core.service import KnowledgeService
from wiki_api.domain.attributes import ItemAttributes, NpcAttributes
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.pipeline.artifact.errors import UnknownEntity, VariantChain
from wiki_api.pipeline.build import build_from_sources
from wiki_api.pipeline.identity import IdentityAllocation, write_allocation
from wiki_api.pipeline.sources.registry import read_sources
from wiki_api.pipeline.sources.staged import StagedSources
from wiki_api.repository.factory import open_repository

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.reporting import BuildReport

SLICES = (
    "item_configs.json",
    "npc_configs.json",
    "shops.json",
    "drop_tables.json",
    "npc_spawns.json",
    "ground_spawns.json",
    "ranged_weapon_configs.json",
    "object_configs.json",
)
CACHE_SLICES = ("items.json", "npcs.json", "scenery.json")
TABLE_SLICES = (
    "Quests",
    "SkillingResource",
    "Stall",
    "CookableItems",
    "SummoningScroll",
    "Consumables",
    "WeaponInterfaces",
)
BUILT_AT = datetime(2026, 8, 3, 12, tzinfo=UTC)
QUESTS = (
    "MYTHS_OF_THE_WHITE_LANDS",
    "BLACK_KNIGHTS_FORTRESS",
    "COOKS_ASSISTANT",
    "DEMON_SLAYER",
    "DORICS_QUEST",
)


def _slice(name: str) -> str:
    from tests.artifact import FIXTURE_KNOWLEDGE

    return (FIXTURE_KNOWLEDGE.parent / "sources" / name).read_text(encoding="utf-8")


def _binary_slice(name: str) -> bytes:
    from tests.artifact import FIXTURE_KNOWLEDGE

    return (FIXTURE_KNOWLEDGE.parent / "sources" / name).read_bytes()


def _staged(root: Path, cache: bool = True) -> StagedSources:
    files: dict[str, str | bytes] = {f"configs/{name}": _slice(name) for name in SLICES}
    for enum in TABLE_SLICES:
        files[f"tables/{enum}.json"] = _slice(_table_slice(enum))
    files["grand-exchange/2024-06-08.json"] = _slice("2024-06-08.json")
    if cache:
        for name in CACHE_SLICES:
            files[f"cache/{name}"] = _slice(f"cache/{name}")
        files["cache/placements.jsonl.gz"] = _binary_slice("cache/placements.jsonl.gz")
    return staged_from(
        root,
        files,
        prices=("grand-exchange/2024-06-08.json",),
        revisions={
            "cache/items.json": "index 19 revision 214",
            "cache/scenery.json": "index 16 revision 330",
        },
    )


def _table_slice(enum: str) -> str:
    return "Quests.json" if enum == "Quests" else f"tables/{enum}.json"


def _identity(root: Path) -> Path:
    directory = root / "identity"
    write_allocation(
        directory,
        IdentityAllocation(
            type=EntityType.QUEST,
            ids={key: number for number, key in enumerate(QUESTS, start=1)},
        ),
    )
    return directory


def _built(root: Path, overlays: Path | None = None) -> tuple[Manifest, BuildReport]:
    _staged(root / "source")
    return build_from_sources(
        root / "source",
        overlays or (root / "overlays"),
        _identity(root),
        root / "knowledge.sqlite3",
        data_version="ingestion-0001",
        built_at=BUILT_AT,
    )


def _rows(
    service: KnowledgeService,
    name: str,
    rel: RelationshipType,
    direction: Direction = Direction.FORWARD,
    types: list[EntityType] | None = None,
) -> int:
    walked = service.walk_by_name(name, rel, direction, types=types)
    assert isinstance(walked.resolution, Found)
    return walked.resolution.value.rows.total


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    _built(tmp_path)
    return tmp_path / "knowledge.sqlite3"


def test_a_slice_of_the_real_sources_builds_an_artifact(tmp_path: Path) -> None:
    manifest, report = _built(tmp_path)
    assert manifest.data_version == "ingestion-0001"
    assert manifest.game_version.repo == "2009scape"
    assert report.entities > 0
    assert report.edges > 0
    assert report.prices > 0


def test_the_same_staged_sources_build_an_identical_artifact(tmp_path: Path) -> None:
    first, _ = _built(tmp_path / "first")
    second, _ = _built(tmp_path / "second")
    assert first.content_hash == second.content_hash
    assert (tmp_path / "first" / "knowledge.sqlite3").read_bytes() == (
        tmp_path / "second" / "knowledge.sqlite3"
    ).read_bytes()


def test_the_order_documents_are_read_in_does_not_change_the_artifact(
    tmp_path: Path,
) -> None:
    staged = _staged(tmp_path / "source")
    allocation = IdentityAllocation(
        type=EntityType.QUEST,
        ids={key: number for number, key in enumerate(QUESTS, start=1)},
    )
    outcomes = read_sources(staged, [], {EntityType.QUEST: allocation})
    forwards = [outcome.read for outcome in outcomes]
    from wiki_api.pipeline.artifact.hashing import content_hash
    from wiki_api.pipeline.artifact.merge import merge

    backwards = list(reversed(forwards))
    assert content_hash(merge(forwards)) == content_hash(merge(backwards))


def test_every_question_the_model_promises_is_answered(artifact: Path) -> None:
    repository = open_repository(artifact)
    service = KnowledgeService(repository)
    try:
        named = service.lookup("Dragon bones", types=[EntityType.ITEM])
        assert isinstance(named.resolution, Found)
        assert named.resolution.value.name == "Dragon bones"
        assert _rows(service, "King Black Dragon", RelationshipType.DROPS) > 0
        assert (
            _rows(
                service,
                "Dragon bones",
                RelationshipType.DROPS,
                Direction.REVERSE,
                types=[EntityType.ITEM],
            )
            > 0
        )
        assert _rows(service, "Edgeville General Store", RelationshipType.SELLS) > 0
        assert repository.list_entities(EntityType.QUEST, limit=1).total == len(QUESTS)
        assert repository.price_history(995)
    finally:
        repository.close()


def test_a_page_descriptor_is_built_from_real_data(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        page = service.get_page(EntityKey(type=EntityType.ITEM, id=4587))
        assert isinstance(page, Found)
        assert page.value.infobox
        assert page.value.entity.label == "Dragon scimitar"
    finally:
        repository.close()


def test_a_noted_item_collapses_onto_the_one_it_copies(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        note = repository.get_entity(EntityKey(type=EntityType.ITEM, id=4588))
        assert note is not None
        assert note.canonical_id == 4587
        assert note.is_variant is True
        assert note.searchable is False
    finally:
        repository.close()


def test_a_name_a_note_used_to_share_now_answers_once(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        named = KnowledgeService(repository).lookup(
            "Dragon scimitar", types=[EntityType.ITEM]
        )
        assert isinstance(named.resolution, Found)
        assert named.resolution.value.key.id == 4587
        assert [link.label for link in named.alternatives] == []
    finally:
        repository.close()


def test_an_item_carries_the_value_every_price_is_worked_out_from(
    artifact: Path,
) -> None:
    repository = open_repository(artifact)
    try:
        item = repository.get_entity(EntityKey(type=EntityType.ITEM, id=4587))
        assert item is not None
        attributes = ItemAttributes.model_validate(item.attributes.model_dump())
        assert attributes.base_value == 100000
        assert attributes.high_alch_value == 60000
        assert attributes.low_alch_value == 40000
    finally:
        repository.close()


def test_an_item_carries_the_weapon_type_its_position_stands_for(
    artifact: Path,
) -> None:
    from wiki_api.domain.vocabulary import WeaponType

    repository = open_repository(artifact)
    try:
        entity = repository.get_entity(EntityKey(type=EntityType.ITEM, id=4587))
        read = ItemAttributes.model_validate(entity.attributes.model_dump())
        assert read.weapon_type is WeaponType.SCIMITAR
    finally:
        repository.close()


def test_a_weapon_list_that_moved_underneath_stops_the_whole_build(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.sources.errors import DriftedVocabulary
    from wiki_api.pipeline.sources.items import check_weapon_types
    from wiki_api.pipeline.staging.declared import WEAPON_TYPES

    staged = _staged(tmp_path / "source")
    moved = json.loads(_slice(f"tables/{WEAPON_TYPES.enum}.json"))
    moved["constants"].insert(0, {"name": "SLING", "values": {"interfaceId": 1}})
    (tmp_path / "source" / WEAPON_TYPES.staged).write_text(
        json.dumps(moved), encoding="utf-8"
    )
    with pytest.raises(DriftedVocabulary):
        check_weapon_types(staged)


def _healing(artifact: Path) -> dict[int, int | None]:
    repository = open_repository(artifact)
    try:
        read: dict[int, int | None] = {}
        for item_id in (2140, 1957, 1511, 536, 2138):
            entity = repository.get_entity(EntityKey(type=EntityType.ITEM, id=item_id))
            read[item_id] = ItemAttributes.model_validate(
                entity.attributes.model_dump()
            ).heals
        return read
    finally:
        repository.close()


def test_an_item_carries_what_the_consumable_table_says_it_restores(
    artifact: Path,
) -> None:
    assert _healing(artifact)[2140] == 3


def test_only_what_the_game_offers_to_eat_or_drink_is_credited(
    artifact: Path,
) -> None:
    read = _healing(artifact)
    assert read[1957] == 11
    assert read[1511] is None


def test_an_effect_buried_in_a_combination_is_not_read(artifact: Path) -> None:
    assert _healing(artifact)[536] is None


def test_an_effect_that_states_a_range_rather_than_an_amount_is_not_read(
    artifact: Path,
) -> None:
    assert _healing(artifact)[2138] is None


def test_the_build_says_how_much_of_the_consumable_table_it_read(
    tmp_path: Path,
) -> None:
    _, report = _built(tmp_path)
    told = "\n".join(line for outcome in report.sources for line in outcome.lines())
    assert "2 items restore an amount the table states outright" in told
    assert "1 named ids the game offers no way to eat or drink" in told


def test_an_npc_carries_the_combat_level_the_cache_holds(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        npc = repository.get_entity(EntityKey(type=EntityType.NPC, id=50))
        assert npc is not None
        attributes = NpcAttributes.model_validate(npc.attributes.model_dump())
        assert attributes.combat_level == 276
    finally:
        repository.close()


def test_a_shop_line_is_priced_once_the_cache_is_staged(tmp_path: Path) -> None:
    _built(tmp_path)
    repository = open_repository(tmp_path / "knowledge.sqlite3")
    try:
        page = repository.edges_from(
            [EntityKey(type=EntityType.SHOP, id=44)],
            rel=RelationshipType.SELLS,
            limit=10,
        )
        priced = [
            edge for edge in page.items if getattr(edge.attributes, "price", None)
        ]
        assert priced
    finally:
        repository.close()


def test_a_build_with_no_staged_cache_still_produces_an_artifact(
    tmp_path: Path,
) -> None:
    _staged(tmp_path / "source", cache=False)
    manifest, report = build_from_sources(
        tmp_path / "source",
        tmp_path / "overlays",
        _identity(tmp_path),
        tmp_path / "knowledge.sqlite3",
        data_version="ingestion-0002",
        built_at=BUILT_AT,
    )
    assert report.entities > 0
    repository = open_repository(tmp_path / "knowledge.sqlite3")
    try:
        note = repository.get_entity(EntityKey(type=EntityType.ITEM, id=4588))
        assert note is not None
        assert note.canonical_id is None
    finally:
        repository.close()
    assert manifest.schema_version >= 5


def test_a_near_name_still_answers_against_real_names(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        near = service.near_names("dragon scimitr", EntityType.ITEM, limit=3)
        assert [row.link.label for row in near.items][:1] == ["Dragon scimitar"]
    finally:
        repository.close()


def test_a_variant_resolves_to_a_canonical_that_is_not_itself_a_variant(
    artifact: Path,
) -> None:
    repository = open_repository(artifact)
    try:
        canonical_key = EntityKey(type=EntityType.ITEM, id=4587)
        variants = repository.variants_of(canonical_key)
        assert variants
        for variant in variants:
            assert variant.canonical_key == canonical_key
        canonical = repository.get_entity(canonical_key)
        assert canonical is not None
        assert canonical.canonical_id is None
    finally:
        repository.close()


def test_an_overlay_collapsing_onto_nothing_fails_the_build(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "variants.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "mode": "patch",
                        "canonical_id": 999_999,
                        "variant_kind": "noted",
                        "searchable": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(UnknownEntity):
        _built(tmp_path, overlays)


def test_an_overlay_pointing_a_variant_at_a_variant_fails_the_build(
    tmp_path: Path,
) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "variants.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "mode": "patch",
                        "canonical_id": 4588,
                        "variant_kind": "noted",
                        "searchable": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(VariantChain):
        _built(tmp_path, overlays)


def test_an_overlay_beats_the_source_it_corrects(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "corrections.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "name": "Coins",
                        "description": "Corrected by hand.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _built(tmp_path, overlays)
    repository = open_repository(tmp_path / "knowledge.sqlite3")
    try:
        entity = repository.get_entity(EntityKey(type=EntityType.ITEM, id=995))
        assert entity is not None
        assert entity.description == "Corrected by hand."
    finally:
        repository.close()


def test_a_spawn_lands_in_a_place_an_overlay_names(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "places.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "location",
                        "id": 1,
                        "name": "Lumbridge",
                        "source_key": "misthalin/lumbridge",
                        "attributes": {
                            "kind": "town",
                            "bounds": {
                                "min_x": 3200,
                                "min_y": 3200,
                                "max_x": 3260,
                                "max_y": 3260,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _, report = _built(tmp_path, overlays)
    placed = [source for source in report.sources if source.source == "npc_spawns.json"]
    assert placed[0].edges > 0


def test_with_no_places_named_no_spawn_becomes_a_placement(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    spawns = [source for source in report.sources if source.source == "npc_spawns.json"]
    assert spawns[0].edges == 0
    assert spawns[0].skipped_by_reason().get("no_place")


def test_a_build_tells_a_reader_what_it_could_not_carry(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    told = "\n".join(report.lines())
    assert "item_configs.json" in told
    assert "source rows did not become facts" in told


def test_a_thing_the_world_holds_becomes_an_entity_of_its_own(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        tree = repository.get_entity(EntityKey(type=EntityType.SCENERY, id=1276))
        assert tree is not None
        assert tree.name == "Tree"
        assert tree.description == "One of the most common trees in 2009Scape."
        assert tree.searchable is True
    finally:
        repository.close()


def test_a_definition_the_world_never_places_is_left_out(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    read = [
        source for source in report.sources if source.source.endswith("scenery.json")
    ]
    assert read[0].entities > 0
    assert read[0].skipped_by_reason().get("no_place")


def test_a_thing_in_the_world_says_what_working_it_gives(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        assert _rows(service, "Tree", RelationshipType.YIELDS) == 1
        assert _rows(service, "Logs", RelationshipType.YIELDS, Direction.REVERSE) == 1
    finally:
        repository.close()


def test_an_item_says_what_it_can_be_turned_into(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        assert _rows(service, "Raw chicken", RelationshipType.MAKES) == 1
        assert (
            _rows(service, "Cooked chicken", RelationshipType.MAKES, Direction.REVERSE)
            == 1
        )
    finally:
        repository.close()


def test_a_decoded_fact_names_its_revision_without_the_staging_manifest(
    artifact: Path,
) -> None:
    repository = open_repository(artifact)
    try:
        tree = repository.get_entity(EntityKey(type=EntityType.SCENERY, id=1276))
        assert tree is not None
        assert tree.provenance.source_revision == "index 16 revision 330"
    finally:
        repository.close()


def test_a_definition_the_source_has_caught_up_with_fails_the_build(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.artifact.errors import OverlayExpired

    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "replaced.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "name": "Coins",
                        "expects": {"name": "Placeholder nobody wrote"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OverlayExpired) as caught:
        _built(tmp_path, overlays)
    assert caught.value.key.id == 995


def test_a_definition_that_still_matches_the_source_builds(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "replaced.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "name": "Coins",
                        "description": "Corrected by hand.",
                        "expects": {"name": "Coins"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _, report = _built(tmp_path, overlays)
    assert report.overridden == 1


def test_a_correction_the_source_has_caught_up_with_fails_the_build(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.artifact.errors import OverlayExpired

    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "expired.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "mode": "patch",
                        "description": "Corrected by hand.",
                        "expects": {"name": "Coin"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(OverlayExpired) as caught:
        _built(tmp_path, overlays)
    assert caught.value.field == "name"
