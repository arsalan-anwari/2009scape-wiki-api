from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from wiki_api.core import (
    Absent,
    Direction,
    Found,
    Hidden,
    Missing,
    Moved,
    PageDescriptor,
)
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType

if TYPE_CHECKING:
    from wiki_api.core import Block, KnowledgeService

SCIMITAR = EntityKey(type=EntityType.ITEM, id=4587)
NOTED_SCIMITAR = EntityKey(type=EntityType.ITEM, id=4588)
DRAGON_BONES = EntityKey(type=EntityType.ITEM, id=536)
WOODEN_STOCK = EntityKey(type=EntityType.ITEM, id=9440)
CLIMBING_BOOTS = EntityKey(type=EntityType.ITEM, id=3105)
KBD = EntityKey(type=EntityType.NPC, id=50)
SHOPKEEPER = EntityKey(type=EntityType.NPC, id=4559)
UNNAMED_NPC = EntityKey(type=EntityType.NPC, id=3089)
CROSSBOW_SHOP = EntityKey(type=EntityType.SHOP, id=53)
DEATH_PLATEAU = EntityKey(type=EntityType.QUEST, id=1)
KBD_LAIR = EntityKey(type=EntityType.LOCATION, id=1)
WHITE_WOLF_MOUNTAIN = EntityKey(type=EntityType.LOCATION, id=3)


def _found[T](resolution: Found[T] | Absent) -> T:
    assert isinstance(resolution, Found), resolution
    return resolution.value


def _page(service: KnowledgeService, key: EntityKey) -> PageDescriptor:
    return _found(service.get_page(key))


def _block(descriptor: PageDescriptor, rel: RelationshipType, way: Direction) -> Block:
    matched = [
        block
        for block in descriptor.blocks
        if block.walk.rel is rel and block.walk.direction is way
    ]
    assert matched, f"no {way.value} block for {rel.value}"
    return matched[0]


# the questions this phase has to answer


def test_what_are_the_details_of_an_item(service: KnowledgeService) -> None:
    descriptor = _page(service, SCIMITAR)
    assert descriptor.entity.label == "Dragon scimitar"
    assert descriptor.description == "A vicious, curved sword."
    shown = {value.key for value in descriptor.infobox} | {
        value.key for section in descriptor.sections for value in section.attributes
    }
    assert "tradeable" in shown
    assert "ge_buy_limit" in shown


def test_what_are_the_stats_of_an_npc(service: KnowledgeService) -> None:
    descriptor = _page(service, KBD)
    values = {
        value.key: value
        for section in descriptor.sections
        for value in section.attributes
    }
    assert values["lifepoints"].value == 240
    assert values["lifepoints"].label == "Lifepoints"


def test_what_is_this_in_one_hover(service: KnowledgeService) -> None:
    tooltip = _found(service.tooltip(KBD))
    assert tooltip.link.label == "King Black Dragon"
    assert {value.key for value in tooltip.attributes} <= {
        "combat_level",
        "lifepoints",
        "combat_style",
        "aggressive",
    }


def test_which_items_does_a_shop_sell(service: KnowledgeService) -> None:
    block = _block(
        _page(service, CROSSBOW_SHOP), RelationshipType.SELLS, Direction.FORWARD
    )
    assert [row.link.key for row in block.rows.items] == [WOODEN_STOCK]
    assert block.label == "Sells"
    values = {value.key: value for value in block.rows.items[0].attributes}
    assert values["price"].value == 8
    assert values["stock_amount"].value == 10


def test_which_shops_sell_an_item(service: KnowledgeService) -> None:
    block = _found(
        service.walk(WOODEN_STOCK, RelationshipType.SELLS, Direction.REVERSE)
    )
    assert [row.link.key for row in block.rows.items] == [CROSSBOW_SHOP]
    assert block.label == "Sold in"


def test_which_items_does_an_npc_drop(service: KnowledgeService) -> None:
    block = _block(_page(service, KBD), RelationshipType.DROPS, Direction.FORWARD)
    assert DRAGON_BONES in {row.link.key for row in block.rows.items}
    values = {value.key: value for value in block.rows.items[0].attributes}
    assert values["denominator"].value == 200.0


def test_which_npcs_drop_an_item(service: KnowledgeService) -> None:
    block = _found(
        service.walk(DRAGON_BONES, RelationshipType.DROPS, Direction.REVERSE)
    )
    assert [row.link.key for row in block.rows.items] == [KBD]
    assert block.label == "Dropped by"


def test_where_is_an_npc_on_the_map(service: KnowledgeService) -> None:
    block = _found(service.walk(KBD, RelationshipType.LOCATED_IN))
    assert [row.link.key for row in block.rows.items] == [KBD_LAIR]
    values = {value.key: value for value in block.rows.items[0].attributes}
    assert values["at"].value == {"x": 2273, "y": 4698, "plane": 0}


def test_what_is_found_at_a_location(service: KnowledgeService) -> None:
    block = _found(
        service.walk(
            WHITE_WOLF_MOUNTAIN, RelationshipType.LOCATED_IN, Direction.REVERSE
        )
    )
    assert {row.link.key for row in block.rows.items} == {CROSSBOW_SHOP, SHOPKEEPER}


def test_which_quests_exist(service: KnowledgeService) -> None:
    listed = service.list_type(EntityType.QUEST)
    assert [summary.link.key for summary in listed.items] == [DEATH_PLATEAU]
    assert listed.items[0].link.label == "Death Plateau"


def test_what_can_i_search_for(service: KnowledgeService) -> None:
    results = service.search("dragon")
    assert results.total >= 2
    assert all(result.score > 0 for result in results.items)
    assert {result.link.key for result in results.items} >= {SCIMITAR, KBD}


def test_the_thing_called_this(service: KnowledgeService) -> None:
    match = service.find("Dragon scimitar")
    assert match.best_match is not None
    assert match.best_match.key == SCIMITAR


def test_a_name_with_no_exact_handle_falls_back_to_the_best_ranked_hit(
    service: KnowledgeService,
) -> None:
    match = service.find("dragon")
    assert match.best_match is not None
    assert match.best_match.key in {result.link.key for result in match.results.items}


def test_a_shorthand_is_a_better_answer_than_a_ranked_guess(
    service: KnowledgeService,
) -> None:
    match = service.find("kbd")
    assert match.best_match is not None
    assert match.best_match.key == KBD


def test_finding_can_be_narrowed_to_one_type(service: KnowledgeService) -> None:
    match = service.find("Dragon scimitar", types=[EntityType.NPC])
    assert match.best_match is None
    assert all(result.type is EntityType.NPC for result in match.results.items)


def test_a_name_nothing_answers_to_finds_nothing(service: KnowledgeService) -> None:
    match = service.find("zzzznotathing")
    assert match.best_match is None
    assert match.results.total == 0


def test_a_name_that_folds_away_to_nothing_finds_nothing(
    service: KnowledgeService,
) -> None:
    match = service.find("!!!")
    assert match.best_match is None
    assert match.results.total == 0


def test_what_did_i_mean_by_this_misspelling(service: KnowledgeService) -> None:
    page = service.near_names("dragon scimtar", EntityType.ITEM)
    assert [result.link.key for result in page.items] == [SCIMITAR]


def test_a_near_name_answer_carries_no_more_than_identity(
    service: KnowledgeService,
) -> None:
    page = service.near_names("dragon scimtar", EntityType.ITEM)
    assert page.items
    for result in page.items:
        assert result.description is None
        assert result.link.label


def test_a_near_name_answer_says_plainly_when_nothing_is_close(
    service: KnowledgeService,
) -> None:
    page = service.near_names("zzzzqqqqwwww", EntityType.ITEM)
    assert page.items == ()
    assert page.total == 0


def test_a_near_name_answer_uses_the_configured_defaults_when_asked_for_none(
    service: KnowledgeService,
) -> None:
    from wiki_api.domain.search import NEAR_LIMIT

    page = service.near_names("dragon", EntityType.ITEM, keep=0.1, floor=0.1)
    assert page.limit == NEAR_LIMIT
    assert len(page.items) <= NEAR_LIMIT


def test_what_types_exist_and_how_they_present(service: KnowledgeService) -> None:
    described = {info.type: info for info in service.describe_types()}
    assert set(described) == set(EntityType)
    assert described[EntityType.NPC].plural == "NPCs"
    assert any(spec.prominent for spec in described[EntityType.NPC].attributes)


def test_which_artifact_am_i_reading(service: KnowledgeService) -> None:
    assert service.about().data_version == "fixture-0001"
    assert service.about().is_readable is True


# resolution


def test_an_entity_resolves_by_its_slug(service: KnowledgeService) -> None:
    entity = _found(service.resolve((EntityType.NPC, "king-black-dragon")))
    assert entity.key == KBD


def test_an_entity_resolves_by_the_text_form_of_its_identity(
    service: KnowledgeService,
) -> None:
    entity = _found(service.resolve("item:4587"))
    assert entity.key == SCIMITAR


def test_a_retired_slug_redirects_to_where_the_entity_lives_now(
    service: KnowledgeService,
) -> None:
    resolution = service.resolve((EntityType.ITEM, "dragon-scimmy"))
    assert isinstance(resolution, Moved)
    assert resolution.target.key == SCIMITAR
    assert resolution.target.label == "Dragon scimitar"
    assert resolution.target.slug == "dragon-scimitar"


def test_a_shorthand_resolves_the_same_way(service: KnowledgeService) -> None:
    resolution = service.resolve((EntityType.NPC, "kbd"))
    assert isinstance(resolution, Moved)
    assert resolution.target.key == KBD


def test_an_unnumbered_type_resolves_by_its_source_key(
    service: KnowledgeService,
) -> None:
    entity = _found(service.resolve((EntityType.QUEST, "DEATH_PLATEAU")))
    assert entity.key == DEATH_PLATEAU


def test_an_unpublished_entity_is_hidden_rather_than_missing(
    service: KnowledgeService,
) -> None:
    resolution = service.resolve(UNNAMED_NPC)
    assert isinstance(resolution, Hidden)
    assert resolution.key == UNNAMED_NPC
    assert resolution.reason is not None


def test_something_that_was_never_there_is_missing(service: KnowledgeService) -> None:
    resolution = service.resolve(EntityKey(type=EntityType.ITEM, id=999999))
    assert isinstance(resolution, Missing)
    assert resolution.reference == "item:999999"


def test_a_reference_that_is_not_even_a_reference_is_missing(
    service: KnowledgeService,
) -> None:
    assert isinstance(service.resolve("not-an-identity"), Missing)


def test_a_handle_that_is_neither_a_slug_nor_a_source_key_is_missing(
    service: KnowledgeService,
) -> None:
    resolution = service.resolve((EntityType.QUEST, "NO_SUCH_QUEST"))
    assert isinstance(resolution, Missing)
    assert resolution.reference == "quest/NO_SUCH_QUEST"


@pytest.mark.parametrize(
    "operation", ["get_page", "tooltip", "resolve"], ids=lambda name: str(name)
)
def test_every_operation_reports_absence_the_same_way(
    service: KnowledgeService, operation: str
) -> None:
    answer = getattr(service, operation)(UNNAMED_NPC)
    assert isinstance(answer, Hidden)


def test_a_walk_from_something_absent_reports_the_absence(
    service: KnowledgeService,
) -> None:
    hidden = service.walk(UNNAMED_NPC, RelationshipType.LOCATED_IN)
    assert isinstance(hidden, Hidden)
    missing = service.walk(
        EntityKey(type=EntityType.NPC, id=999999), RelationshipType.DROPS
    )
    assert isinstance(missing, Missing)


# variants


def test_a_reverse_walk_finds_what_was_recorded_against_a_variant(
    service: KnowledgeService,
) -> None:
    block = _found(service.walk(SCIMITAR, RelationshipType.DROPS, Direction.REVERSE))
    assert [row.link.key for row in block.rows.items] == [KBD]
    assert block.rows.total == 1


def test_a_variant_has_its_own_page_pointing_at_the_canonical_entity(
    service: KnowledgeService,
) -> None:
    descriptor = _page(service, NOTED_SCIMITAR)
    assert descriptor.canonical is not None
    assert descriptor.canonical.key == SCIMITAR
    assert descriptor.variants == ()


def test_a_canonical_page_links_to_its_variants(service: KnowledgeService) -> None:
    descriptor = _page(service, SCIMITAR)
    assert [link.key for link in descriptor.variants] == [NOTED_SCIMITAR]
    assert descriptor.canonical is None


def test_a_variant_page_shows_the_relationships_of_the_real_thing(
    service: KnowledgeService,
) -> None:
    canonical = _block(
        _page(service, SCIMITAR), RelationshipType.DROPS, Direction.REVERSE
    )
    variant = _block(
        _page(service, NOTED_SCIMITAR), RelationshipType.DROPS, Direction.REVERSE
    )
    assert [row.link.key for row in variant.rows.items] == [
        row.link.key for row in canonical.rows.items
    ]


# blocks


def test_a_block_carries_the_walk_that_fetches_its_next_page(
    service: KnowledgeService,
) -> None:
    block = _block(_page(service, KBD), RelationshipType.DROPS, Direction.FORWARD)
    again = _found(
        service.walk(block.walk.origin, block.walk.rel, block.walk.direction)
    )
    assert [row.link.key for row in again.rows.items] == [
        row.link.key for row in block.rows.items
    ]


def test_a_block_that_would_be_empty_is_left_off_the_page(
    service: KnowledgeService,
) -> None:
    descriptor = _page(service, DRAGON_BONES)
    assert all(not block.is_empty for block in descriptor.blocks)
    walked = {(block.walk.rel, block.walk.direction) for block in descriptor.blocks}
    assert (RelationshipType.SELLS, Direction.REVERSE) not in walked


def test_blocks_are_ordered_the_way_the_registry_declares(
    service: KnowledgeService,
) -> None:
    orders = [block.order for block in _page(service, SCIMITAR).blocks]
    assert orders == sorted(orders)


def test_a_page_reads_the_variant_set_once_rather_than_once_per_block(
    fixture_manifest: object,
    fixture_snapshot: object,
) -> None:
    from wiki_api.core import KnowledgeService as Service
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityKey as Key
    from wiki_api.repository.memory import InMemoryKnowledgeRepository

    class Counting(InMemoryKnowledgeRepository):
        calls = 0

        def variants_of(self, key: Key) -> tuple[Entity, ...]:
            type(self).calls += 1
            return super().variants_of(key)

    repository = Counting(
        fixture_manifest,  # type: ignore[arg-type]
        entities=fixture_snapshot.entities,  # type: ignore[attr-defined]
        edges=fixture_snapshot.edges,  # type: ignore[attr-defined]
    )
    Counting.calls = 0
    descriptor = _page(Service(repository), SCIMITAR)
    assert len(descriptor.blocks) >= 1
    assert Counting.calls == 1


def test_a_page_block_holds_a_preview_rather_than_everything(
    service: KnowledgeService,
) -> None:
    from wiki_api.core import BLOCK_PAGE_SIZE

    descriptor = _page(service, KBD)
    for block in descriptor.blocks:
        assert block.rows.limit == BLOCK_PAGE_SIZE
        assert block.rows.limit < service.list_type(EntityType.NPC).limit


def test_a_walk_pages_through_a_relationship_without_gaps(
    service: KnowledgeService,
) -> None:
    collected: list[EntityKey] = []
    offset = 0
    while True:
        block = _found(
            service.walk(KBD, RelationshipType.DROPS, limit=1, offset=offset)
        )
        collected.extend(row.link.key for row in block.rows.items)
        if block.rows.next_offset is None:
            break
        offset = block.rows.next_offset
    assert len(collected) == len(set(collected)) == 3


def test_a_hidden_neighbour_never_reaches_a_block(service: KnowledgeService) -> None:
    block = _found(
        service.walk(
            WHITE_WOLF_MOUNTAIN, RelationshipType.LOCATED_IN, Direction.REVERSE
        )
    )
    assert UNNAMED_NPC not in {row.link.key for row in block.rows.items}
    assert block.rows.total == len(block.rows.items)
    assert block.suppressed == 0


def test_a_block_row_carries_identity_and_never_a_url(
    service: KnowledgeService,
) -> None:
    block = _block(_page(service, KBD), RelationshipType.DROPS, Direction.FORWARD)
    row = block.rows.items[0]
    assert row.link.slug
    assert row.link.label
    assert "http" not in row.model_dump_json()


# the promise the registries make


def test_nothing_in_the_core_names_an_attribute_or_a_relationship() -> None:
    import re
    from pathlib import Path

    import wiki_api.core as core
    from tests.vocabulary import declared_names

    forbidden = declared_names()
    for path in Path(str(core.__path__[0])).glob("*.py"):
        source = path.read_text(encoding="utf-8").split("\n# test cases\n")[0]
        named = {
            word for word in forbidden if re.search(rf"\b{re.escape(word)}\b", source)
        }
        assert not named, f"{path.name} names {sorted(named)}"


def test_a_descriptor_needs_no_knowledge_of_the_fields_it_shows(
    service: KnowledgeService,
) -> None:
    for descriptor in (
        _page(service, SCIMITAR),
        _page(service, KBD),
        _page(service, CROSSBOW_SHOP),
        _page(service, DEATH_PLATEAU),
        _page(service, KBD_LAIR),
    ):
        shown = list(descriptor.infobox) + [
            value for section in descriptor.sections for value in section.attributes
        ]
        assert all(value.label for value in shown)
        assert all(value.format for value in shown)


def test_every_relationship_a_type_can_have_is_reachable_from_the_registry(
    service: KnowledgeService,
) -> None:
    described = {info.type: info for info in service.describe_types()}
    for entity_type, info in described.items():
        for spec in info.relationships:
            assert entity_type in spec.src_types or entity_type in spec.dst_types


# gaps in the data itself


def _service_with_a_dangling_edge() -> KnowledgeService:
    from datetime import UTC, datetime

    from wiki_api.core import KnowledgeService as Service
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.manifest import SCHEMA_VERSION, Manifest
    from wiki_api.domain.relationships import Edge
    from wiki_api.repository.memory import InMemoryKnowledgeRepository

    provenance = {"source": "fixture", "game_version": "test"}
    dragon = Entity.model_validate(
        {
            "key": {"type": "npc", "id": 50},
            "slug": "king-black-dragon",
            "name": "King Black Dragon",
            "attributes": {},
            "provenance": provenance,
        }
    )
    bones = Entity.model_validate(
        {
            "key": {"type": "item", "id": 536},
            "slug": "dragon-bones",
            "name": "Dragon bones",
            "attributes": {},
            "provenance": provenance,
        }
    )
    edges = [
        Edge.model_validate(
            {
                "src": {"type": "npc", "id": 50},
                "rel": "drops",
                "dst": {"type": "item", "id": target},
                "attributes": {"weight": 1.0, "denominator": 128.0},
                "provenance": provenance,
            }
        )
        for target in (536, 999999)
    ]
    manifest = Manifest.model_validate(
        {
            "data_version": "gap-0001",
            "schema_version": SCHEMA_VERSION,
            "content_hash": "0" * 64,
            "built_at": datetime(2026, 7, 29, tzinfo=UTC),
            "game_version": "2009scape@0000000",
        }
    )
    return Service(
        InMemoryKnowledgeRepository(manifest, entities=[dragon, bones], edges=edges)
    )


def test_an_edge_that_leads_nowhere_is_counted_rather_than_rendered() -> None:
    service = _service_with_a_dangling_edge()
    block = _found(service.walk(KBD, RelationshipType.DROPS))
    assert [row.link.key for row in block.rows.items] == [DRAGON_BONES]
    assert block.suppressed == 1
    assert block.rows.total == 2


def test_a_page_still_renders_around_a_gap_in_the_data() -> None:
    service = _service_with_a_dangling_edge()
    descriptor = _page(service, KBD)
    block = _block(descriptor, RelationshipType.DROPS, Direction.FORWARD)
    assert block.suppressed == 1
    assert descriptor.entity.label == "King Black Dragon"


def _service_with_a_dangling_alias() -> KnowledgeService:
    from datetime import UTC, datetime

    from wiki_api.core import KnowledgeService as Service
    from wiki_api.domain.alias import AliasKind, EntityAlias
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.manifest import SCHEMA_VERSION, Manifest
    from wiki_api.repository.memory import InMemoryKnowledgeRepository

    ghost = Entity.model_validate(
        {
            "key": {"type": "npc", "id": 7},
            "slug": "ghost",
            "name": "Ghost",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    aliases = [
        EntityAlias(
            type=EntityType.ITEM,
            slug="ghost",
            entity_id=999999,
            kind=AliasKind.RETIRED_SLUG,
        )
    ]
    manifest = Manifest.model_validate(
        {
            "data_version": "gap-0002",
            "schema_version": SCHEMA_VERSION,
            "content_hash": "0" * 64,
            "built_at": datetime(2026, 7, 29, tzinfo=UTC),
            "game_version": "2009scape@0000000",
        }
    )
    return Service(
        InMemoryKnowledgeRepository(manifest, entities=[ghost], aliases=aliases)
    )


def test_a_redirect_to_something_that_is_not_there_is_missing() -> None:
    service = _service_with_a_dangling_alias()
    resolution = service.resolve((EntityType.ITEM, "ghost"))
    assert isinstance(resolution, Missing)
    assert resolution.reference == "item:999999"


def test_a_handle_that_leads_nowhere_in_one_type_is_tried_in_the_next() -> None:
    service = _service_with_a_dangling_alias()
    match = service.find("Ghost")
    assert match.best_match is not None
    assert match.best_match.key == EntityKey(type=EntityType.NPC, id=7)
