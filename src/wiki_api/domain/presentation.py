"""Where a group of attributes belongs on a page and what an entity type is called,
declared rather than written in code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from wiki_api.domain.identity import EntityType
from wiki_api.domain.vocabulary import AttributeGroup, GameEnum

if TYPE_CHECKING:
    from collections.abc import Mapping


class GroupPlacement(GameEnum):
    """Where the attributes of one group belong: the infobox, a section, or kept in the
    data but not shown.
    """

    INFOBOX = "infobox"
    SECTION = "section"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class GroupMeta:
    """What one attribute group is called and where it belongs."""

    label: str
    placement: GroupPlacement
    order: int


@dataclass(frozen=True)
class EntityTypeMeta:
    """What one entity type is called, in the singular and the plural."""

    label: str
    plural: str
    order: int


GROUP_META: Final[Mapping[AttributeGroup, GroupMeta]] = {
    AttributeGroup.OVERVIEW: GroupMeta("Overview", GroupPlacement.INFOBOX, 10),
    AttributeGroup.GENERAL: GroupMeta("General", GroupPlacement.INFOBOX, 20),
    AttributeGroup.MAP: GroupMeta("Location", GroupPlacement.INFOBOX, 30),
    AttributeGroup.COMBAT: GroupMeta("Combat", GroupPlacement.SECTION, 40),
    AttributeGroup.EQUIPMENT: GroupMeta("Equipment", GroupPlacement.SECTION, 50),
    AttributeGroup.TRADE: GroupMeta("Trade", GroupPlacement.SECTION, 60),
    AttributeGroup.BEHAVIOUR: GroupMeta("Behaviour", GroupPlacement.SECTION, 70),
    AttributeGroup.DROPS: GroupMeta("Drops", GroupPlacement.SECTION, 80),
    AttributeGroup.SHOP: GroupMeta("Shop", GroupPlacement.SECTION, 90),
    AttributeGroup.RATE: GroupMeta("Rate", GroupPlacement.SECTION, 100),
    AttributeGroup.AMOUNT: GroupMeta("Amount", GroupPlacement.SECTION, 110),
    AttributeGroup.REWARD: GroupMeta("Reward", GroupPlacement.SECTION, 120),
    AttributeGroup.INTERNAL: GroupMeta("Internal", GroupPlacement.HIDDEN, 999),
}

ENTITY_TYPE_META: Final[Mapping[EntityType, EntityTypeMeta]] = {
    EntityType.ITEM: EntityTypeMeta("Item", "Items", 10),
    EntityType.NPC: EntityTypeMeta("NPC", "NPCs", 20),
    EntityType.SHOP: EntityTypeMeta("Shop", "Shops", 30),
    EntityType.QUEST: EntityTypeMeta("Quest", "Quests", 40),
    EntityType.LOCATION: EntityTypeMeta("Location", "Locations", 50),
}


def placement_of(group: AttributeGroup) -> GroupPlacement:
    """Where the attributes of one group belong on a page."""
    return GROUP_META[group].placement


# test cases


def test_every_attribute_group_declares_how_it_presents() -> None:
    for group in AttributeGroup:
        meta = GROUP_META[group]
        assert meta.label
        assert isinstance(meta.placement, GroupPlacement)


def test_every_entity_type_declares_a_singular_and_a_plural() -> None:
    for entity_type in EntityType:
        meta = ENTITY_TYPE_META[entity_type]
        assert meta.label
        assert meta.plural
        assert meta.plural != meta.label


def test_group_order_is_unambiguous() -> None:
    orders = [meta.order for meta in GROUP_META.values()]
    assert len(set(orders)) == len(orders)


def test_entity_type_order_is_unambiguous() -> None:
    orders = [meta.order for meta in ENTITY_TYPE_META.values()]
    assert len(set(orders)) == len(orders)


def test_internal_attributes_are_never_placed_on_a_page() -> None:
    assert placement_of(AttributeGroup.INTERNAL) is GroupPlacement.HIDDEN


def test_a_page_has_both_an_infobox_and_body_sections() -> None:
    placements = {meta.placement for meta in GROUP_META.values()}
    assert GroupPlacement.INFOBOX in placements
    assert GroupPlacement.SECTION in placements
