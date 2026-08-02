"""Describe a whole page as data, so a reader can render one mechanically."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import PageDescriptor, Section
from wiki_api.core.values import entity_values
from wiki_api.core.walks import BLOCK_PAGE_SIZE, blocks_of
from wiki_api.domain.presentation import GROUP_META, GroupPlacement

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.core.results import AttributeValue, Block
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import Link
    from wiki_api.domain.vocabulary import AttributeGroup
    from wiki_api.repository.protocol import KnowledgeRepository


def describe_page(
    repository: KnowledgeRepository,
    entity: Entity,
    *,
    data_version: str,
    limit: int = BLOCK_PAGE_SIZE,
) -> PageDescriptor:
    """Describe everything a reader needs to render this entity's page."""
    canonical_key = entity.canonical_key
    variants = repository.variants_of(canonical_key)
    keys = tuple(dict.fromkeys([canonical_key, *(variant.key for variant in variants)]))
    return build_descriptor(
        entity,
        blocks=blocks_of(repository, entity, keys, limit=limit),
        canonical=_canonical_link(repository, entity),
        variants=(
            ()
            if entity.is_variant
            else tuple(variant.to_link() for variant in variants)
        ),
        data_version=data_version,
    )


def build_descriptor(
    entity: Entity,
    *,
    blocks: Sequence[Block],
    canonical: Link | None,
    variants: Sequence[Link],
    data_version: str,
) -> PageDescriptor:
    """Lay an entity out from the values it holds and the blocks already walked."""
    values = entity_values(entity)
    return PageDescriptor(
        entity=entity.to_link(),
        type=entity.type,
        description=entity.description,
        canonical=canonical,
        variants=tuple(variants),
        infobox=infobox_of(values),
        sections=sections_of(values),
        blocks=tuple(blocks),
        data_version=data_version,
    )


def infobox_of(values: Sequence[AttributeValue]) -> tuple[AttributeValue, ...]:
    """Collect the values shown beside the page rather than inside it."""
    chosen = [
        value
        for value in values
        if GROUP_META[value.group].placement is GroupPlacement.INFOBOX
    ]
    chosen.sort(key=lambda value: (GROUP_META[value.group].order, value.order))
    return tuple(chosen)


def sections_of(values: Sequence[AttributeValue]) -> tuple[Section, ...]:
    """Build the page body, one section per group that has anything to show."""
    grouped: dict[AttributeGroup, list[AttributeValue]] = {}
    for value in values:
        if GROUP_META[value.group].placement is not GroupPlacement.SECTION:
            continue
        grouped.setdefault(value.group, []).append(value)
    sections = [
        Section(
            group=group,
            label=GROUP_META[group].label,
            placement=GROUP_META[group].placement,
            order=GROUP_META[group].order,
            attributes=tuple(sorted(held, key=lambda value: value.order)),
        )
        for group, held in grouped.items()
    ]
    sections.sort(key=lambda section: section.order)
    return tuple(sections)


def _canonical_link(repository: KnowledgeRepository, entity: Entity) -> Link | None:
    if not entity.is_variant:
        return None
    found = repository.get_entities([entity.canonical_key])
    canonical = found.get(entity.canonical_key)
    return None if canonical is None else canonical.to_link()


# test cases


def _entity(**overrides: object) -> Entity:
    from wiki_api.domain.entity import Entity

    payload: dict[str, object] = {
        "key": {"type": "item", "id": 4587},
        "slug": "dragon-scimitar",
        "name": "Dragon scimitar",
        "description": "A vicious, curved sword.",
        "attributes": {
            "tradeable": True,
            "shop_price": 100,
            "weight": 1.8,
            "equipment_slot": 3,
            "weapon_interface": 18,
        },
        "provenance": {"source": "fixture", "game_version": "test"},
    }
    payload.update(overrides)
    return Entity.model_validate(payload)


def _descriptor() -> PageDescriptor:
    return build_descriptor(
        _entity(),
        blocks=(),
        canonical=None,
        variants=(),
        data_version="fixture-0001",
    )


def test_a_descriptor_carries_identity_rather_than_a_url() -> None:
    descriptor = _descriptor()
    assert descriptor.entity.slug == "dragon-scimitar"
    assert descriptor.entity.label == "Dragon scimitar"
    assert descriptor.data_version == "fixture-0001"


def test_values_are_split_between_the_infobox_and_the_body() -> None:
    descriptor = _descriptor()
    infobox = {value.key for value in descriptor.infobox}
    sectioned = {
        value.key for section in descriptor.sections for value in section.attributes
    }
    assert infobox
    assert sectioned
    assert not infobox & sectioned


def test_a_section_is_labelled_and_ordered_by_the_registry() -> None:
    descriptor = _descriptor()
    orders = [section.order for section in descriptor.sections]
    assert orders == sorted(orders)
    assert all(section.label for section in descriptor.sections)


def test_a_group_with_nothing_to_show_is_not_a_section() -> None:
    from wiki_api.domain.vocabulary import AttributeGroup

    descriptor = _descriptor()
    groups = {section.group for section in descriptor.sections}
    assert AttributeGroup.COMBAT not in groups


def test_internal_values_reach_neither_the_infobox_nor_a_section() -> None:
    descriptor = _descriptor()
    shown = {value.key for value in descriptor.infobox} | {
        value.key for section in descriptor.sections for value in section.attributes
    }
    assert "weapon_interface" not in shown


def test_a_page_with_no_attributes_at_all_still_describes_itself() -> None:
    descriptor = build_descriptor(
        _entity(attributes={}),
        blocks=(),
        canonical=None,
        variants=(),
        data_version="fixture-0001",
    )
    assert descriptor.infobox == ()
    assert descriptor.sections == ()
    assert descriptor.entity.label == "Dragon scimitar"
