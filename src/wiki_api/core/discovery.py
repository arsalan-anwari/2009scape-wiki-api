"""Finding things without knowing their identity, and saying what there is to find.

Searching ranks; finding decides. A caller that means one particular thing gets it,
because a name that is an exact handle beats whatever a full text score put first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import EntitySummary, Match, SearchResult, TypeInfo
from wiki_api.domain.attributes import ATTRIBUTE_SPECS
from wiki_api.domain.errors import EntityMoved, EntityNotFound
from wiki_api.domain.identity import EntityType
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page, SortOrder
from wiki_api.domain.presentation import ENTITY_TYPE_META
from wiki_api.domain.relationships import RELATIONSHIP_SPECS
from wiki_api.domain.slug import slugify

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityKey, Link
    from wiki_api.repository.protocol import KnowledgeRepository


def search(
    repository: KnowledgeRepository,
    query: str,
    *,
    types: Sequence[EntityType] | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> Page[SearchResult]:
    """Whatever matches the words a caller typed, best first."""
    hits = repository.search(query, types=types, limit=limit, offset=offset)
    return Page[SearchResult](
        items=tuple(
            SearchResult(
                link=hit.entity.to_link(),
                type=hit.entity.type,
                description=hit.entity.description,
                score=hit.score,
            )
            for hit in hits.items
        ),
        total=hits.total,
        limit=hits.limit,
        offset=hits.offset,
    )


def find(
    repository: KnowledgeRepository,
    name: str,
    *,
    types: Sequence[EntityType] | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> Match:
    """The thing called this, plus everything else the words matched."""
    results = search(repository, name, types=types, limit=limit)
    exact = _by_handle(repository, slugify(name), types)
    if exact is None and results.items:
        return Match(best_match=results.items[0].link, results=results)
    return Match(best_match=exact, results=results)


def list_type(
    repository: KnowledgeRepository,
    entity_type: EntityType,
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    order: SortOrder = SortOrder.NAME,
) -> Page[EntitySummary]:
    """One page of an index."""
    listed = repository.list_entities(
        entity_type, limit=limit, offset=offset, order=order
    )
    return Page[EntitySummary](
        items=tuple(_summary(entity) for entity in listed.items),
        total=listed.total,
        limit=listed.limit,
        offset=listed.offset,
    )


def describe_types() -> tuple[TypeInfo, ...]:
    """What kinds of thing exist, and how each one's values present.

    This is the whole registry as a reader sees it, and the only way it leaves the core.
    """
    described = [
        TypeInfo(
            type=entity_type,
            label=meta.label,
            plural=meta.plural,
            order=meta.order,
            attributes=ATTRIBUTE_SPECS[entity_type],
            relationships=tuple(
                spec
                for spec in sorted(
                    RELATIONSHIP_SPECS.values(), key=lambda spec: spec.order
                )
                if entity_type in spec.src_types or entity_type in spec.dst_types
            ),
        )
        for entity_type, meta in ENTITY_TYPE_META.items()
    ]
    described.sort(key=lambda info: info.order)
    return tuple(described)


def _summary(entity: Entity) -> EntitySummary:
    return EntitySummary(
        link=entity.to_link(), type=entity.type, description=entity.description
    )


def _by_handle(
    repository: KnowledgeRepository,
    handle: str,
    types: Sequence[EntityType] | None,
) -> Link | None:
    """The entity whose slug or alias is exactly this, searched in type order."""
    if not handle:
        return None
    wanted = tuple(types) if types else tuple(_in_declared_order())
    for entity_type in wanted:
        key = _handle_key(repository, entity_type, handle)
        if key is None:
            continue
        found = repository.get_entities([key])
        entity = found.get(key)
        if entity is not None:
            return entity.to_link()
    return None


def _handle_key(
    repository: KnowledgeRepository, entity_type: EntityType, handle: str
) -> EntityKey | None:
    try:
        return repository.resolve_slug(entity_type, handle)
    except EntityMoved as moved:
        return moved.target
    except EntityNotFound:
        return None


def _in_declared_order() -> tuple[EntityType, ...]:
    return tuple(
        entity_type
        for entity_type, _ in sorted(
            ENTITY_TYPE_META.items(), key=lambda entry: entry[1].order
        )
    )


# test cases


def test_every_type_is_described_with_its_own_registry() -> None:
    described = describe_types()
    assert {info.type for info in described} == set(EntityType)
    for info in described:
        assert info.attributes
        assert info.label
        assert info.plural


def test_a_type_is_described_with_the_relationships_it_can_take_part_in() -> None:
    from wiki_api.domain.relationships import RelationshipType

    by_type = {info.type: info for info in describe_types()}
    quest_rels = {spec.rel for spec in by_type[EntityType.QUEST].relationships}
    assert RelationshipType.REWARDS in quest_rels
    assert RelationshipType.SELLS not in quest_rels


def test_types_are_described_in_a_declared_order() -> None:
    orders = [info.order for info in describe_types()]
    assert orders == sorted(orders)


def test_the_types_a_handle_is_looked_up_in_are_ordered() -> None:
    assert _in_declared_order()[0] is EntityType.ITEM


def test_a_summary_carries_identity_and_nothing_a_reader_cannot_use() -> None:
    from wiki_api.domain.entity import Entity

    entity = Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "description": "A vicious, curved sword.",
            "attributes": {"tradeable": True},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    summary = _summary(entity)
    assert summary.link.slug == "dragon-scimitar"
    assert summary.description == "A vicious, curved sword."
