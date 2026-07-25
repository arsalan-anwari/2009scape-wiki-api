from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from wiki_api.domain.page import DEFAULT_PAGE_SIZE, SortOrder

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.page import Page
    from wiki_api.domain.prices import PricePoint
    from wiki_api.domain.relationships import Edge, RelationshipType
    from wiki_api.domain.search import SearchHit


@runtime_checkable
class KnowledgeRepository(Protocol):
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

    def search(
        self,
        query: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[SearchHit]: ...

    def edges_from(
        self,
        key: EntityKey,
        *,
        rel: RelationshipType | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]: ...

    def edges_to(
        self,
        key: EntityKey,
        *,
        rel: RelationshipType | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]: ...

    def variants_of(self, key: EntityKey) -> tuple[Entity, ...]: ...

    def price_history(
        self, item_id: int, *, since: date | None = None
    ) -> tuple[PricePoint, ...]: ...

    def close(self) -> None: ...


def test_the_protocol_describes_the_whole_read_surface() -> None:
    operations = {name for name in dir(KnowledgeRepository) if not name.startswith("_")}
    assert operations == {
        "manifest",
        "get_entity",
        "get_entities",
        "resolve_slug",
        "resolve_source_key",
        "list_entities",
        "search",
        "edges_from",
        "edges_to",
        "variants_of",
        "price_history",
        "close",
    }


def test_every_listing_operation_is_paginated() -> None:
    import inspect

    for name in ("list_entities", "search", "edges_from", "edges_to"):
        signature = inspect.signature(getattr(KnowledgeRepository, name))
        assert {"limit", "offset"} <= set(signature.parameters)
        assert signature.return_annotation.startswith("Page[")


def test_the_protocol_is_read_only() -> None:
    forbidden = ("save", "insert", "update", "delete", "write", "commit")
    operations = {name.lower() for name in dir(KnowledgeRepository)}
    assert not any(word in name for name in operations for word in forbidden)
