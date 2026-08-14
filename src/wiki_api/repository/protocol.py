"""Declare the one read interface every storage backend satisfies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from wiki_api.domain.page import DEFAULT_PAGE_SIZE, SortOrder
from wiki_api.domain.search import NEAR_FLOOR, NEAR_KEEP, NEAR_LIMIT

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.page import Page
    from wiki_api.domain.prices import PricePoint
    from wiki_api.domain.query import Condition, Ordering
    from wiki_api.domain.relationships import Edge, RelationshipType
    from wiki_api.domain.search import SearchHit


@runtime_checkable
class KnowledgeRepository(Protocol):
    """Everything the query core asks of storage: read only, every listing paged, every
    walk taking a set of keys.
    """

    def manifest(self) -> Manifest: ...

    def get_entity(self, key: EntityKey, *, include_hidden: bool = False) -> Entity: ...

    def get_entities(self, keys: Sequence[EntityKey]) -> Mapping[EntityKey, Entity]: ...

    def resolve_slug(self, entity_type: EntityType, slug: str) -> EntityKey: ...

    def resolve_source_key(
        self, entity_type: EntityType, source_key: str
    ) -> EntityKey: ...

    def list_entities(
        self,
        entity_type: EntityType,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order: SortOrder = SortOrder.NAME,
    ) -> Page[Entity]: ...

    def list_by_attribute(
        self,
        entity_type: EntityType,
        *,
        where: Sequence[Condition] = (),
        order: Ordering | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Entity]: ...

    def search(
        self,
        query: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[SearchHit]: ...

    def nearest(
        self,
        query: str,
        entity_type: EntityType,
        *,
        limit: int = NEAR_LIMIT,
        keep: float = NEAR_KEEP,
        floor: float = NEAR_FLOOR,
    ) -> Page[SearchHit]: ...

    def edges_from(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        sorts: Sequence[EntityType] | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]: ...

    def edges_to(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        sorts: Sequence[EntityType] | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]: ...

    def variants_of(self, key: EntityKey) -> tuple[Entity, ...]: ...

    def relationship_totals(self) -> Mapping[RelationshipType, int]: ...

    def price_history(
        self, item_id: int, *, since: date | None = None
    ) -> tuple[PricePoint, ...]: ...

    def close(self) -> None: ...


# test cases


def test_the_protocol_describes_the_whole_read_surface() -> None:
    operations = {name for name in dir(KnowledgeRepository) if not name.startswith("_")}
    assert operations == {
        "manifest",
        "get_entity",
        "get_entities",
        "resolve_slug",
        "resolve_source_key",
        "list_entities",
        "list_by_attribute",
        "search",
        "nearest",
        "edges_from",
        "edges_to",
        "variants_of",
        "relationship_totals",
        "price_history",
        "close",
    }


def test_every_listing_operation_is_paginated() -> None:
    import inspect

    for name in (
        "list_entities",
        "list_by_attribute",
        "search",
        "edges_from",
        "edges_to",
    ):
        signature = inspect.signature(getattr(KnowledgeRepository, name))
        assert {"limit", "offset"} <= set(signature.parameters)
        assert signature.return_annotation.startswith("Page[")


def test_a_walk_can_be_narrowed_to_the_sorts_a_caller_wants() -> None:
    import inspect

    for name in ("edges_from", "edges_to"):
        signature = inspect.signature(getattr(KnowledgeRepository, name))
        narrowing = signature.parameters["sorts"]
        assert narrowing.default is None
        assert narrowing.kind is inspect.Parameter.KEYWORD_ONLY


def test_a_near_name_question_is_always_about_one_sort_of_thing() -> None:
    import inspect

    signature = inspect.signature(KnowledgeRepository.nearest)
    assert signature.parameters["entity_type"].annotation == "EntityType"
    assert signature.parameters["entity_type"].default is inspect.Parameter.empty


def test_a_near_name_answer_is_bounded_without_being_paged() -> None:
    import inspect

    signature = inspect.signature(KnowledgeRepository.nearest)
    assert "limit" in signature.parameters
    assert "offset" not in signature.parameters


def test_a_walk_takes_a_set_of_keys_so_variants_travel_with_the_canonical() -> None:
    import inspect

    for name in ("edges_from", "edges_to"):
        signature = inspect.signature(getattr(KnowledgeRepository, name))
        assert signature.parameters["keys"].annotation == "Sequence[EntityKey]"


def test_a_walk_can_be_asked_to_keep_unpublished_neighbours() -> None:
    import inspect

    for name in ("edges_from", "edges_to"):
        signature = inspect.signature(getattr(KnowledgeRepository, name))
        parameter = signature.parameters["include_hidden"]
        assert parameter.default is False
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_protocol_is_read_only() -> None:
    forbidden = ("save", "insert", "update", "delete", "write", "commit")
    operations = {name.lower() for name in dir(KnowledgeRepository)}
    assert not any(word in name for name in operations for word in forbidden)
