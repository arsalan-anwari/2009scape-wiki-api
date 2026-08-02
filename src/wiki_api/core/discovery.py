"""Find things without knowing their identity, and say what there is to find.

Searching ranks; finding decides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.resolution import Reference, entity_of, resolve
from wiki_api.core.results import (
    EntityResolution,
    EntitySummary,
    Match,
    Missing,
    Named,
    SearchResult,
    TypeInfo,
)
from wiki_api.domain.attributes import ATTRIBUTE_SPECS
from wiki_api.domain.entity import Entity
from wiki_api.domain.errors import EntityMoved, EntityNotFound
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page, SortOrder
from wiki_api.domain.presentation import ENTITY_TYPE_META
from wiki_api.domain.relationships import RELATIONSHIP_SPECS
from wiki_api.domain.search import NEAR_FLOOR, NEAR_KEEP, NEAR_LIMIT
from wiki_api.domain.slug import slugify

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.domain.identity import Link
    from wiki_api.repository.protocol import KnowledgeRepository


def search(
    repository: KnowledgeRepository,
    query: str,
    *,
    types: Sequence[EntityType] | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> Page[SearchResult]:
    """Rank whatever matches the words a caller typed, best first."""
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
    """Decide which one thing a name means, with everything else it matched."""
    results = search(repository, name, types=types, limit=limit)
    exact = _by_handle(repository, slugify(name), types)
    if exact is None and results.items:
        return Match(best_match=results.items[0].link, results=results)
    return Match(best_match=exact, results=results)


def lookup(
    repository: KnowledgeRepository,
    name: str,
    *,
    types: Sequence[EntityType] | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> Named[Entity]:
    """Resolve a name or a written identity to one entity, with whatever else the
    words matched.
    """
    written = _written_identity(name, types)
    if written is not None:
        resolved = resolve(repository, written)
        if not isinstance(resolved, Missing):
            return _named(resolved)
    match = find(repository, name, types=types, limit=limit)
    if match.best_match is None:
        return Named[Entity](resolution=Missing(reference=name))
    return _named(
        resolve(repository, match.best_match.key),
        alternatives=_besides(match, match.best_match),
    )


def near_names(
    repository: KnowledgeRepository,
    name: str,
    entity_type: EntityType,
    *,
    limit: int = NEAR_LIMIT,
    keep: float = NEAR_KEEP,
    floor: float = NEAR_FLOOR,
) -> Page[SearchResult]:
    """Return the real names a misspelt one may have meant, or nothing when none is
    close enough.

    Each candidate carries identity only, so whoever asked has to choose one and ask
    again rather than be answered from a guess.
    """
    hits = repository.nearest(name, entity_type, limit=limit, keep=keep, floor=floor)
    return Page[SearchResult](
        items=tuple(
            SearchResult(
                link=hit.entity.to_link(),
                type=hit.entity.type,
                description=None,
                score=hit.score,
            )
            for hit in hits.items
        ),
        total=hits.total,
        limit=hits.limit,
        offset=hits.offset,
    )


def list_type(
    repository: KnowledgeRepository,
    entity_type: EntityType,
    *,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    order: SortOrder = SortOrder.NAME,
) -> Page[EntitySummary]:
    """Read one page of an index."""
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
    """Publish the registry: what sorts of thing exist, and how each one's values
    present.
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


def _written_identity(
    name: str, types: Sequence[EntityType] | None
) -> Reference | None:
    """Read an identity a caller wrote out, which counts only when they narrowed the
    question to one type.
    """
    text = name.strip()
    if not text:
        return None
    if text.isdigit():
        if types is not None and len(types) == 1:
            return EntityKey(type=types[0], id=int(text))
        return None
    try:
        return EntityKey.parse(text)
    except ValueError:
        return None


def _named(
    resolution: EntityResolution, alternatives: tuple[Link, ...] = ()
) -> Named[Entity]:
    found = entity_of(resolution)
    return Named[Entity](
        resolution=resolution,
        subject=found.to_link() if found is not None else None,
        alternatives=alternatives,
    )


def _besides(match: Match, chosen: Link) -> tuple[Link, ...]:
    return tuple(
        result.link for result in match.results.items if result.link.key != chosen.key
    )


def _summary(entity: Entity) -> EntitySummary:
    return EntitySummary(
        link=entity.to_link(), type=entity.type, description=entity.description
    )


def _by_handle(
    repository: KnowledgeRepository,
    handle: str,
    types: Sequence[EntityType] | None,
) -> Link | None:
    """Find the entity whose slug or alias is exactly this, searched in type order."""
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


def test_a_written_identity_is_taken_at_its_word() -> None:
    assert _written_identity("item:4587", None) == EntityKey(
        type=EntityType.ITEM, id=4587
    )


def test_a_bare_number_only_identifies_something_once_a_type_is_known() -> None:
    assert _written_identity("4587", None) is None
    assert _written_identity("4587", [EntityType.ITEM, EntityType.NPC]) is None
    assert _written_identity("4587", [EntityType.ITEM]) == EntityKey(
        type=EntityType.ITEM, id=4587
    )


def test_a_name_is_never_mistaken_for_an_identity() -> None:
    assert _written_identity("Dragon scimitar", [EntityType.ITEM]) is None
    assert _written_identity("  ", [EntityType.ITEM]) is None


def test_the_thing_a_caller_picked_is_not_offered_back_as_an_alternative() -> None:
    from wiki_api.domain.identity import Link as EntityLink

    chosen = EntityLink(
        type=EntityType.ITEM, id=4587, slug="dragon-scimitar", label="Dragon scimitar"
    )
    other = EntityLink(
        type=EntityType.ITEM, id=4588, slug="dragon-scimitar-4588", label="Dragon scim"
    )
    match = Match(
        best_match=chosen,
        results=Page[SearchResult](
            items=(
                SearchResult(link=chosen, type=EntityType.ITEM, score=2.0),
                SearchResult(link=other, type=EntityType.ITEM, score=1.0),
            ),
            total=2,
            limit=DEFAULT_PAGE_SIZE,
            offset=0,
        ),
    )
    assert _besides(match, chosen) == (other,)


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
