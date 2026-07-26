from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from wiki_api.domain.entity import VariantKind
from wiki_api.domain.errors import EntityHidden, EntityMoved, EntityNotFound
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.page import SortOrder
from wiki_api.domain.relationships import (
    RELATIONSHIP_SPECS,
    DropEdgeAttributes,
    RelationshipType,
)
from wiki_api.domain.vocabulary import COINS, Skill, SourceKind

if TYPE_CHECKING:
    from wiki_api.repository.protocol import KnowledgeRepository

SCIMITAR = EntityKey(type=EntityType.ITEM, id=4587)
NOTED_SCIMITAR = EntityKey(type=EntityType.ITEM, id=4588)
DRAGON_BONES = EntityKey(type=EntityType.ITEM, id=536)
KBD_HEADS = EntityKey(type=EntityType.ITEM, id=7980)
CLIMBING_BOOTS = EntityKey(type=EntityType.ITEM, id=3105)
WOODEN_STOCK = EntityKey(type=EntityType.ITEM, id=9440)
VAMBRACES = EntityKey(type=EntityType.ITEM, id=1065)
HOLY_WATER = EntityKey(type=EntityType.ITEM, id=732)
CROSSBOW = EntityKey(type=EntityType.ITEM, id=767)
BRONZE_BOLTS = EntityKey(type=EntityType.ITEM, id=877)
KBD = EntityKey(type=EntityType.NPC, id=50)
SHOPKEEPER = EntityKey(type=EntityType.NPC, id=4559)
UNNAMED_NPC = EntityKey(type=EntityType.NPC, id=3089)
CROSSBOW_SHOP = EntityKey(type=EntityType.SHOP, id=53)
DEATH_PLATEAU = EntityKey(type=EntityType.QUEST, id=1)
KBD_LAIR = EntityKey(type=EntityType.LOCATION, id=1)
WILDERNESS = EntityKey(type=EntityType.LOCATION, id=2)
WHITE_WOLF_MOUNTAIN = EntityKey(type=EntityType.LOCATION, id=3)
BURTHORPE = EntityKey(type=EntityType.LOCATION, id=4)


def test_the_repository_satisfies_the_protocol(
    repository: KnowledgeRepository,
) -> None:
    from wiki_api.repository.protocol import KnowledgeRepository as Contract

    assert isinstance(repository, Contract)


def test_the_manifest_describes_the_artifact(repository: KnowledgeRepository) -> None:
    manifest = repository.manifest()
    assert manifest.is_readable is True
    assert manifest.data_version == "fixture-0001"
    assert str(manifest.game_version) == "2009scape@5a37f2f8"
    assert manifest.game_commit == "5a37f2f8"
    assert len(manifest.content_hash) == 64


def test_an_entity_is_fetched_by_identity(repository: KnowledgeRepository) -> None:
    entity = repository.get_entity(SCIMITAR)
    assert entity.name == "Dragon scimitar"
    assert entity.description == "A vicious, curved sword."
    assert entity.slug == "dragon-scimitar-4587"
    assert entity.provenance.source is SourceKind.GAME_CONFIG
    assert entity.provenance.source_file == "item_configs.json"


def test_type_specific_attributes_survive_the_round_trip(
    repository: KnowledgeRepository,
) -> None:
    from wiki_api.domain.attributes import ItemAttributes, NpcAttributes

    item = repository.get_entity(SCIMITAR)
    assert isinstance(item.attributes, ItemAttributes)
    assert item.attributes.ge_buy_limit == 10
    assert item.attributes.bonuses is not None
    assert item.attributes.bonuses.attack_slash == 67
    assert item.attributes.bonuses.attack_crush == -2
    assert item.attributes.bonuses.strength == 66
    assert item.attributes.requirements is not None
    assert item.attributes.requirements[0].skill is Skill.ATTACK
    assert item.attributes.requirements is not None
    assert item.attributes.requirements[0].level == 60

    npc = repository.get_entity(KBD)
    assert isinstance(npc.attributes, NpcAttributes)
    assert npc.attributes.lifepoints == 240
    assert npc.attributes.slayer_exp == 258.0


def test_a_missing_entity_is_reported_as_such(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityNotFound):
        repository.get_entity(EntityKey(type=EntityType.ITEM, id=999999))


def test_a_hidden_entity_is_distinct_from_a_missing_one(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityHidden) as raised:
        repository.get_entity(UNNAMED_NPC)
    assert raised.value.reason == "unnamed"
    hidden = repository.get_entity(UNNAMED_NPC, include_hidden=True)
    assert hidden.is_published is False
    assert hidden.slug == "npc-3089"


def test_entities_are_resolved_in_one_batch(
    repository: KnowledgeRepository,
) -> None:
    absent = EntityKey(type=EntityType.ITEM, id=1)
    found = repository.get_entities([SCIMITAR, KBD, absent])
    assert set(found) == {SCIMITAR, KBD}
    assert found[KBD].name == "King Black Dragon"


def test_an_empty_batch_asks_nothing(repository: KnowledgeRepository) -> None:
    assert repository.get_entities([]) == {}


def test_a_slug_resolves_to_its_entity(repository: KnowledgeRepository) -> None:
    assert repository.resolve_slug(EntityType.ITEM, "dragon-scimitar-4587") == SCIMITAR
    assert repository.resolve_slug(EntityType.NPC, "king-black-dragon") == KBD


def test_a_retired_slug_redirects_instead_of_disappearing(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityMoved) as raised:
        repository.resolve_slug(EntityType.ITEM, "dragon-scimmy")
    assert raised.value.target == SCIMITAR


def test_a_readable_alias_points_at_the_canonical_entity(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityMoved) as raised:
        repository.resolve_slug(EntityType.ITEM, "dragon-scimitar")
    assert raised.value.target == SCIMITAR


def test_an_alias_is_scoped_to_its_type(repository: KnowledgeRepository) -> None:
    with pytest.raises(EntityNotFound):
        repository.resolve_slug(EntityType.ITEM, "kbd")


def test_an_unknown_slug_is_not_found(repository: KnowledgeRepository) -> None:
    with pytest.raises(EntityNotFound):
        repository.resolve_slug(EntityType.ITEM, "no-such-thing")


def test_listing_a_type_is_paginated_and_ordered_by_name(
    repository: KnowledgeRepository,
) -> None:
    first = repository.list_entities(EntityType.ITEM, limit=3, offset=0)
    assert [entity.name for entity in first.items] == [
        "Bronze bolts",
        "Climbing boots",
        "Coins",
    ]
    assert first.has_more is True
    second = repository.list_entities(EntityType.ITEM, limit=3, offset=3)
    assert first.total == second.total
    assert not set(first.items) & set(second.items)


def test_listing_can_be_ordered_by_identity(
    repository: KnowledgeRepository,
) -> None:
    listed = repository.list_entities(EntityType.ITEM, limit=4, order=SortOrder.ID)
    assert [entity.key.id for entity in listed.items] == [536, 732, 767, 877]


def test_index_pages_show_neither_variants_nor_hidden_entities(
    repository: KnowledgeRepository,
) -> None:
    items = repository.list_entities(EntityType.ITEM, limit=50)
    assert NOTED_SCIMITAR not in {entity.key for entity in items.items}
    npcs = repository.list_entities(EntityType.NPC, limit=50)
    assert {entity.key for entity in npcs.items} == {KBD, SHOPKEEPER}


def test_every_entity_type_can_be_listed(repository: KnowledgeRepository) -> None:
    for entity_type in EntityType:
        assert repository.list_entities(entity_type, limit=50).total >= 1


def test_paging_past_the_end_is_empty_but_valid(
    repository: KnowledgeRepository,
) -> None:
    page = repository.list_entities(EntityType.QUEST, limit=10, offset=10)
    assert page.items == ()
    assert page.total == 1
    assert page.next_offset is None


def test_search_finds_an_entity_by_name(repository: KnowledgeRepository) -> None:
    hits = repository.search("king black dragon", types=[EntityType.NPC])
    assert [hit.entity.key for hit in hits.items] == [KBD]


def test_search_spans_every_type_including_places(
    repository: KnowledgeRepository,
) -> None:
    keys = {hit.entity.key for hit in repository.search("king black dragon").items}
    assert {KBD, KBD_LAIR} <= keys


def test_search_matches_a_prefix_for_a_type_ahead_box(
    repository: KnowledgeRepository,
) -> None:
    keys = {hit.entity.key for hit in repository.search("climb").items}
    assert CLIMBING_BOOTS in keys


def test_search_collapses_variants_to_one_result(
    repository: KnowledgeRepository,
) -> None:
    hits = repository.search("dragon scimitar")
    assert [hit.entity.key for hit in hits.items] == [SCIMITAR]
    assert hits.total == 1


def test_search_never_returns_hidden_entities(
    repository: KnowledgeRepository,
) -> None:
    for query in ("npc 3089", "npc-3089"):
        keys = {hit.entity.key for hit in repository.search(query).items}
        assert UNNAMED_NPC not in keys


def test_a_name_match_outranks_a_description_match(
    repository: KnowledgeRepository,
) -> None:
    hits = repository.search("dragon", limit=50)
    scores = {hit.entity.key: hit.score for hit in hits.items}
    assert DRAGON_BONES in scores
    assert VAMBRACES in scores
    assert scores[DRAGON_BONES] > scores[VAMBRACES]


def test_search_can_be_narrowed_to_one_type(
    repository: KnowledgeRepository,
) -> None:
    hits = repository.search("dragon", types=[EntityType.NPC], limit=50)
    assert {hit.entity.key.type for hit in hits.items} == {EntityType.NPC}


def test_search_finds_an_entity_by_community_shorthand(
    repository: KnowledgeRepository,
) -> None:
    keys = {hit.entity.key for hit in repository.search("dscim").items}
    assert keys == {SCIMITAR}


def test_search_results_are_paginated(repository: KnowledgeRepository) -> None:
    first = repository.search("dragon", limit=1, offset=0)
    assert len(first.items) == 1
    assert first.total > 1
    second = repository.search("dragon", limit=1, offset=1)
    assert first.items[0].entity.key != second.items[0].entity.key


def test_a_query_with_no_searchable_characters_returns_nothing(
    repository: KnowledgeRepository,
) -> None:
    page = repository.search("   ")
    assert page.items == ()
    assert page.total == 0


def test_a_query_that_matches_nothing_returns_an_empty_page(
    repository: KnowledgeRepository,
) -> None:
    page = repository.search("zzzznotathing")
    assert page.items == ()
    assert page.total == 0


def test_search_requires_every_token_to_match(
    repository: KnowledgeRepository,
) -> None:
    assert repository.search("dragon zzzznotathing").total == 0


def test_a_relationship_is_walked_forwards(repository: KnowledgeRepository) -> None:
    drops = repository.edges_from(KBD, rel=RelationshipType.DROPS)
    assert [edge.dst for edge in drops.items] == [DRAGON_BONES, KBD_HEADS]


def test_a_relationship_is_walked_backwards(repository: KnowledgeRepository) -> None:
    dropped_by = repository.edges_to(KBD_HEADS, rel=RelationshipType.DROPS)
    assert [edge.src for edge in dropped_by.items] == [KBD]
    assert RELATIONSHIP_SPECS[dropped_by.items[0].rel].inverse_label == "Dropped by"


def test_edge_attributes_survive_the_round_trip(
    repository: KnowledgeRepository,
) -> None:
    tertiary = repository.edges_to(KBD_HEADS, rel=RelationshipType.DROPS).items[0]
    assert isinstance(tertiary.attributes, DropEdgeAttributes)
    assert tertiary.attributes.weight == 1.0
    assert tertiary.attributes.denominator == 128.0
    assert tertiary.attributes.one_in == 128.0
    assert tertiary.discriminator == "tertiary"


def test_walking_without_a_relationship_filter_returns_every_edge(
    repository: KnowledgeRepository,
) -> None:
    walked = repository.edges_from(CROSSBOW_SHOP)
    assert walked.total == 3
    assert {edge.rel for edge in walked.items} == {
        RelationshipType.SELLS,
        RelationshipType.STAFFED_BY,
        RelationshipType.LOCATED_IN,
    }


def test_a_reverse_lookup_is_paginated_so_a_common_item_cannot_flood_a_caller(
    repository: KnowledgeRepository,
) -> None:
    first = repository.edges_from(CROSSBOW_SHOP, limit=1, offset=0)
    assert len(first.items) == 1
    assert first.total == 3
    assert first.has_more is True
    assert first.next_offset == 1
    second = repository.edges_from(CROSSBOW_SHOP, limit=1, offset=1)
    assert second.items[0] != first.items[0]
    last = repository.edges_from(CROSSBOW_SHOP, limit=1, offset=2)
    assert last.has_more is False


def test_a_walk_past_the_end_is_empty_but_still_reports_the_total(
    repository: KnowledgeRepository,
) -> None:
    page = repository.edges_to(KBD_HEADS, rel=RelationshipType.DROPS, offset=50)
    assert page.items == ()
    assert page.total == 1
    assert page.next_offset is None


def test_a_shop_relationship_carries_price_and_stock(
    repository: KnowledgeRepository,
) -> None:
    from wiki_api.domain.relationships import SellEdgeAttributes

    sells = repository.edges_from(CROSSBOW_SHOP, rel=RelationshipType.SELLS).items[0]
    assert sells.dst == WOODEN_STOCK
    assert isinstance(sells.attributes, SellEdgeAttributes)
    assert sells.attributes.stock_amount == 10
    assert sells.attributes.price == 8
    assert sells.attributes.currency == COINS


def test_a_quest_reward_is_a_reverse_lookup_from_the_item(
    repository: KnowledgeRepository,
) -> None:
    rewards = repository.edges_to(CLIMBING_BOOTS, rel=RelationshipType.REWARDS)
    assert [edge.src for edge in rewards.items] == [DEATH_PLATEAU]
    assert RELATIONSHIP_SPECS[rewards.items[0].rel].inverse_label == "Reward from"


def test_an_entity_with_no_relationships_returns_nothing(
    repository: KnowledgeRepository,
) -> None:
    page = repository.edges_from(EntityKey(type=EntityType.ITEM, id=995))
    assert page.items == ()
    assert page.total == 0


def test_variants_are_reachable_from_their_canonical_entity(
    repository: KnowledgeRepository,
) -> None:
    variants = repository.variants_of(SCIMITAR)
    assert [variant.key for variant in variants] == [NOTED_SCIMITAR]
    assert variants[0].variant_kind is VariantKind.NOTED
    assert variants[0].searchable is False


def test_a_variant_is_still_addressable_by_identity(
    repository: KnowledgeRepository,
) -> None:
    variant = repository.get_entity(NOTED_SCIMITAR)
    assert variant.canonical_key == SCIMITAR


def test_an_entity_without_variants_has_none(
    repository: KnowledgeRepository,
) -> None:
    assert repository.variants_of(KBD) == ()


def test_price_history_comes_back_in_date_order(
    repository: KnowledgeRepository,
) -> None:
    points = repository.price_history(4587)
    assert [point.snapshot_date for point in points] == [
        date(2024, 6, 8),
        date(2024, 6, 15),
        date(2026, 7, 18),
        date(2026, 7, 25),
    ]
    assert points[-1].value == 108590


def test_price_history_can_start_from_a_date(
    repository: KnowledgeRepository,
) -> None:
    points = repository.price_history(4587, since=date(2026, 1, 1))
    assert [point.value for point in points] == [108601, 108590]


def test_a_noted_variant_keeps_its_own_prices(
    repository: KnowledgeRepository,
) -> None:
    assert {point.value for point in repository.price_history(4588)} == {100000}


def test_an_unpriced_item_has_no_history(repository: KnowledgeRepository) -> None:
    assert repository.price_history(7980) == ()


def test_an_overlay_correction_is_what_the_repository_serves(
    repository: KnowledgeRepository,
) -> None:
    corrected = repository.get_entity(EntityKey(type=EntityType.ITEM, id=14422))
    assert corrected.name == "Sacred clay pouch (class 1)"
    assert corrected.provenance.source is SourceKind.OVERLAY
    shop = repository.get_entity(CROSSBOW_SHOP)
    assert shop.name == "Crossbow Shop (White Wolf Mountain)"


def test_a_link_carries_identity_and_a_label(
    repository: KnowledgeRepository,
) -> None:
    link = repository.get_entity(SCIMITAR).to_link()
    assert link.model_dump() == {
        "type": EntityType.ITEM,
        "id": 4587,
        "slug": "dragon-scimitar-4587",
        "label": "Dragon scimitar",
        "icon_ref": None,
    }


def test_a_same_type_relationship_is_walked_in_both_directions(
    repository: KnowledgeRepository,
) -> None:
    forward = repository.edges_from(CROSSBOW, rel=RelationshipType.USES_AMMUNITION)
    assert [edge.dst for edge in forward.items] == [BRONZE_BOLTS]
    assert RELATIONSHIP_SPECS[forward.items[0].rel].forward_label == "Uses ammunition"

    inverse = repository.edges_to(BRONZE_BOLTS, rel=RelationshipType.USES_AMMUNITION)
    assert [edge.src for edge in inverse.items] == [CROSSBOW]
    assert RELATIONSHIP_SPECS[inverse.items[0].rel].inverse_label == "Used by"


def test_a_same_type_relationship_does_not_leak_between_directions(
    repository: KnowledgeRepository,
) -> None:
    ammunition = RelationshipType.USES_AMMUNITION
    assert repository.edges_to(CROSSBOW, rel=ammunition).items == ()
    assert repository.edges_from(BRONZE_BOLTS, rel=ammunition).items == ()


def test_an_entity_related_to_itself_appears_in_both_directions(
    repository: KnowledgeRepository,
) -> None:
    forward = repository.edges_from(HOLY_WATER, rel=RelationshipType.USES_AMMUNITION)
    inverse = repository.edges_to(HOLY_WATER, rel=RelationshipType.USES_AMMUNITION)
    assert [edge.dst for edge in forward.items] == [HOLY_WATER]
    assert [edge.src for edge in inverse.items] == [HOLY_WATER]
    assert forward == inverse


def test_an_unnumbered_entity_is_reachable_by_its_source_key(
    repository: KnowledgeRepository,
) -> None:
    assert repository.resolve_source_key(EntityType.QUEST, "DEATH_PLATEAU") == (
        DEATH_PLATEAU
    )
    assert repository.get_entity(DEATH_PLATEAU).source_key == "DEATH_PLATEAU"


def test_a_numbered_entity_carries_no_source_key(
    repository: KnowledgeRepository,
) -> None:
    assert repository.get_entity(SCIMITAR).source_key is None


def test_source_keys_are_scoped_to_their_type(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityNotFound):
        repository.resolve_source_key(EntityType.ITEM, "DEATH_PLATEAU")


def test_an_unknown_source_key_is_not_found(
    repository: KnowledgeRepository,
) -> None:
    with pytest.raises(EntityNotFound):
        repository.resolve_source_key(EntityType.QUEST, "NO_SUCH_QUEST")


def test_the_natural_key_survives_a_rebuild_that_reassigns_nothing(
    repository: KnowledgeRepository,
) -> None:
    key = repository.resolve_source_key(EntityType.QUEST, "DEATH_PLATEAU")
    entity = repository.get_entity(key)
    assert entity.slug == "death-plateau"
    assert entity.provenance.source is SourceKind.OVERLAY


def test_where_an_npc_is_found_on_the_map(repository: KnowledgeRepository) -> None:
    from wiki_api.domain.relationships import LocatedInEdgeAttributes
    from wiki_api.domain.space import SpawnKind

    found = repository.edges_from(KBD, rel=RelationshipType.LOCATED_IN)
    assert [edge.dst for edge in found.items] == [KBD_LAIR]
    spawn = found.items[0]
    assert isinstance(spawn.attributes, LocatedInEdgeAttributes)
    assert spawn.attributes.at is not None
    assert (spawn.attributes.at.x, spawn.attributes.at.y) == (2273, 4698)
    assert spawn.attributes.at.region_id == 9033
    assert spawn.attributes.spawn_kind is SpawnKind.NPC_SPAWN


def test_where_a_shop_is_found_on_the_map(repository: KnowledgeRepository) -> None:
    found = repository.edges_from(CROSSBOW_SHOP, rel=RelationshipType.LOCATED_IN)
    assert [edge.dst for edge in found.items] == [WHITE_WOLF_MOUNTAIN]
    place = repository.get_entity(found.items[0].dst)
    assert place.name == "White Wolf Mountain"


def test_a_place_whose_exact_tile_is_unknown_is_still_a_place(
    repository: KnowledgeRepository,
) -> None:
    from wiki_api.domain.attributes import LocationAttributes
    from wiki_api.domain.relationships import LocatedInEdgeAttributes

    place = repository.get_entity(WHITE_WOLF_MOUNTAIN)
    assert isinstance(place.attributes, LocationAttributes)
    assert place.attributes.anchor is None
    found = repository.edges_from(CROSSBOW_SHOP, rel=RelationshipType.LOCATED_IN)
    edge = found.items[0]
    assert isinstance(edge.attributes, LocatedInEdgeAttributes)
    assert edge.attributes.at is None
    assert edge.discriminator == ""


def test_what_is_found_in_a_place_is_the_reverse_walk(
    repository: KnowledgeRepository,
) -> None:
    here = repository.edges_to(WHITE_WOLF_MOUNTAIN, rel=RelationshipType.LOCATED_IN)
    assert {edge.src for edge in here.items} == {CROSSBOW_SHOP, SHOPKEEPER}
    assert RELATIONSHIP_SPECS[here.items[0].rel].inverse_label == "Found here"


def test_a_place_carries_its_own_position(repository: KnowledgeRepository) -> None:
    from wiki_api.domain.attributes import LocationAttributes
    from wiki_api.domain.space import Coordinate, LocationKind

    lair = repository.get_entity(KBD_LAIR)
    assert isinstance(lair.attributes, LocationAttributes)
    assert lair.attributes.kind is LocationKind.DUNGEON
    assert lair.attributes.centre == Coordinate(x=2273, y=4698, plane=0)
    assert lair.attributes.region_id == 9033


def test_a_place_carries_an_extent_when_a_single_tile_would_lie(
    repository: KnowledgeRepository,
) -> None:
    from wiki_api.domain.attributes import LocationAttributes
    from wiki_api.domain.space import Coordinate

    wilderness = repository.get_entity(WILDERNESS)
    assert isinstance(wilderness.attributes, LocationAttributes)
    assert wilderness.attributes.bounds is not None
    assert wilderness.attributes.bounds.contains(Coordinate(x=3200, y=3600))
    assert wilderness.attributes.anchor is not None


def test_places_nest_so_a_question_can_be_answered_at_any_zoom(
    repository: KnowledgeRepository,
) -> None:
    upward = repository.edges_from(KBD_LAIR, rel=RelationshipType.PART_OF)
    assert [edge.dst for edge in upward.items] == [WILDERNESS]
    downward = repository.edges_to(WILDERNESS, rel=RelationshipType.PART_OF)
    assert [edge.src for edge in downward.items] == [KBD_LAIR]
    assert RELATIONSHIP_SPECS[downward.items[0].rel].inverse_label == "Contains"


def test_places_are_listed_and_resolved_like_every_other_type(
    repository: KnowledgeRepository,
) -> None:
    listed = repository.list_entities(EntityType.LOCATION, limit=50)
    assert {entity.key for entity in listed.items} == {
        KBD_LAIR,
        WILDERNESS,
        WHITE_WOLF_MOUNTAIN,
        BURTHORPE,
    }
    assert repository.resolve_slug(EntityType.LOCATION, "wilderness") == WILDERNESS
    assert repository.resolve_source_key(EntityType.LOCATION, "wilderness") == (
        WILDERNESS
    )
