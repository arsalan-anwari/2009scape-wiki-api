"""Back the repository with objects in memory, for tests and small tools."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from wiki_api.domain.entity import Entity
from wiki_api.domain.errors import (
    EntityHidden,
    EntityMoved,
    EntityNotFound,
    IncompatibleArtifact,
)
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.manifest import SCHEMA_VERSION
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page, SortOrder
from wiki_api.domain.relationships import Edge
from wiki_api.domain.search import NEAR_FLOOR, NEAR_KEEP, NEAR_LIMIT, SearchHit
from wiki_api.repository.naming import NameIndex, fold

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date

    from wiki_api.domain.alias import EntityAlias
    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.prices import PricePoint
    from wiki_api.domain.relationships import RelationshipType

NAME_WEIGHT = 10.0
ALIAS_WEIGHT = 5.0
DESCRIPTION_WEIGHT = 1.0

_TOKENS = re.compile(r"[0-9a-z]+")


class InMemoryKnowledgeRepository:
    """The same read interface as SQLite, answered straight from a snapshot."""

    def __init__(
        self,
        manifest: Manifest,
        entities: Sequence[Entity] = (),
        edges: Sequence[Edge] = (),
        aliases: Sequence[EntityAlias] = (),
        prices: Sequence[PricePoint] = (),
    ) -> None:
        if not manifest.is_readable:
            raise IncompatibleArtifact(manifest.schema_version, SCHEMA_VERSION)
        self._manifest = manifest
        self._entities = {entity.key: entity for entity in entities}
        self._edges = tuple(edges)
        self._aliases = {(alias.type, alias.slug): alias for alias in aliases}
        self._slugs = {
            (entity.key.type, entity.slug): entity.key for entity in entities
        }
        self._source_keys = {
            (entity.key.type, entity.source_key): entity.key
            for entity in entities
            if entity.source_key is not None
        }
        self._prices = tuple(prices)
        self._alias_terms = _alias_terms(aliases)
        self._names: dict[EntityType, NameIndex] = {}

    def manifest(self) -> Manifest:
        return self._manifest

    def get_entity(self, key: EntityKey, *, include_hidden: bool = False) -> Entity:
        entity = self._entities.get(key)
        if entity is None:
            raise EntityNotFound(str(key))
        if not include_hidden and not entity.is_published:
            raise EntityHidden(key, entity.hidden_reason)
        return entity

    def get_entities(self, keys: Sequence[EntityKey]) -> Mapping[EntityKey, Entity]:
        found = {}
        for key in keys:
            entity = self._entities.get(key)
            if entity is not None:
                found[key] = entity
        return found

    def resolve_slug(self, entity_type: EntityType, slug: str) -> EntityKey:
        key = self._slugs.get((entity_type, slug))
        if key is not None:
            return key
        alias = self._aliases.get((entity_type, slug))
        if alias is not None:
            raise EntityMoved(slug, alias.key)
        raise EntityNotFound(f"{entity_type.value}/{slug}")

    def resolve_source_key(self, entity_type: EntityType, source_key: str) -> EntityKey:
        key = self._source_keys.get((entity_type, source_key))
        if key is None:
            raise EntityNotFound(f"{entity_type.value}#{source_key}")
        return key

    def list_entities(
        self,
        entity_type: EntityType,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order: SortOrder = SortOrder.NAME,
    ) -> Page[Entity]:
        listed = [
            entity
            for entity in self._entities.values()
            if entity.key.type is entity_type
            and entity.is_published
            and entity.canonical_id is None
        ]
        if order is SortOrder.NAME:
            listed.sort(key=lambda entity: (entity.name, entity.key.id))
        else:
            listed.sort(key=lambda entity: entity.key.id)
        return Page[Entity](
            items=tuple(listed[offset : offset + limit]),
            total=len(listed),
            limit=limit,
            offset=offset,
        )

    def search(
        self,
        query: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[SearchHit]:
        tokens = _tokens(query)
        if not tokens:
            return Page[SearchHit](items=(), total=0, limit=limit, offset=offset)
        wanted = frozenset(types) if types else frozenset(EntityType)
        scored: list[SearchHit] = []
        for entity in self._entities.values():
            if entity.key.type not in wanted or not entity.searchable:
                continue
            if not entity.is_published:
                continue
            score = self._score(entity, tokens)
            if score is not None:
                scored.append(SearchHit(entity=entity, score=score))
        scored.sort(key=lambda hit: (-hit.score, hit.entity.name, hit.entity.key.id))
        return Page[SearchHit](
            items=tuple(scored[offset : offset + limit]),
            total=len(scored),
            limit=limit,
            offset=offset,
        )

    def nearest(
        self,
        query: str,
        entity_type: EntityType,
        *,
        limit: int = NEAR_LIMIT,
        keep: float = NEAR_KEEP,
        floor: float = NEAR_FLOOR,
    ) -> Page[SearchHit]:
        found = self._name_index(entity_type).near(
            query, limit=limit, keep=keep, floor=floor
        )
        hits = tuple(
            SearchHit(entity=self._entities[nearby.key], score=nearby.score)
            for nearby in found
            if nearby.key in self._entities
        )
        return Page[SearchHit](items=hits, total=len(hits), limit=limit, offset=0)

    def edges_from(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]:
        wanted = frozenset(keys)
        matched = [
            edge
            for edge in self._edges
            if edge.src in wanted
            and (rel is None or edge.rel is rel)
            and (include_hidden or not self._is_hidden(edge.dst))
        ]
        matched.sort(
            key=lambda edge: (
                edge.rel.value,
                edge.order_key,
                edge.dst.type.value,
                edge.dst.id,
                edge.discriminator,
                edge.src.type.value,
                edge.src.id,
            )
        )
        return _edge_page(matched, limit, offset)

    def edges_to(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]:
        wanted = frozenset(keys)
        matched = [
            edge
            for edge in self._edges
            if edge.dst in wanted
            and (rel is None or edge.rel is rel)
            and (include_hidden or not self._is_hidden(edge.src))
        ]
        matched.sort(
            key=lambda edge: (
                edge.rel.value,
                edge.order_key,
                edge.src.type.value,
                edge.src.id,
                edge.discriminator,
                edge.dst.type.value,
                edge.dst.id,
            )
        )
        return _edge_page(matched, limit, offset)

    def variants_of(self, key: EntityKey) -> tuple[Entity, ...]:
        variants = [
            entity
            for entity in self._entities.values()
            if entity.key.type is key.type and entity.canonical_id == key.id
        ]
        variants.sort(key=lambda entity: entity.key.id)
        return tuple(variants)

    def price_history(
        self, item_id: int, *, since: date | None = None
    ) -> tuple[PricePoint, ...]:
        points = [
            point
            for point in self._prices
            if point.item_id == item_id
            and (since is None or point.snapshot_date >= since)
        ]
        points.sort(key=lambda point: point.snapshot_date)
        return tuple(points)

    def close(self) -> None:
        return None

    def _name_index(self, entity_type: EntityType) -> NameIndex:
        held = self._names.get(entity_type)
        if held is not None:
            return held
        built = NameIndex(
            (entity.key, entity.name)
            for entity in self._entities.values()
            if entity.key.type is entity_type and entity.searchable
        )
        self._names[entity_type] = built
        return built

    def _is_hidden(self, key: EntityKey) -> bool:
        entity = self._entities.get(key)
        return entity is not None and not entity.is_published

    def _score(self, entity: Entity, tokens: Sequence[str]) -> float | None:
        total = 0.0
        name = fold(entity.name)
        description = fold(entity.description or "")
        aliases = self._alias_terms.get(entity.key, "")
        for token in tokens:
            weight = 0.0
            if _has_prefix(name, token):
                weight = NAME_WEIGHT
            elif _has_prefix(aliases, token):
                weight = ALIAS_WEIGHT
            elif _has_prefix(description, token):
                weight = DESCRIPTION_WEIGHT
            if weight == 0.0:
                return None
            total += weight
        return total


def _edge_page(matched: Sequence[Edge], limit: int, offset: int) -> Page[Edge]:
    return Page[Edge](
        items=tuple(matched[offset : offset + limit]),
        total=len(matched),
        limit=limit,
        offset=offset,
    )


def _tokens(query: str) -> tuple[str, ...]:
    return tuple(_TOKENS.findall(fold(query)))


def _has_prefix(haystack: str, token: str) -> bool:
    return any(word.startswith(token) for word in _TOKENS.findall(haystack))


def _alias_terms(aliases: Sequence[EntityAlias]) -> dict[EntityKey, str]:
    grouped: dict[EntityKey, list[str]] = {}
    for alias in aliases:
        grouped.setdefault(alias.key, []).append(alias.slug.replace("-", " "))
    return {key: " ".join(terms) for key, terms in grouped.items()}


# test cases


def test_folding_matches_the_near_name_rules() -> None:
    assert fold("Café AU Lait") == "cafe au lait"
    assert fold("Green d'hide") == "green d'hide"


def test_a_query_becomes_alphanumeric_tokens() -> None:
    assert _tokens("Dragon scimitar") == ("dragon", "scimitar")
    assert _tokens("d'hide (green)") == ("d", "hide", "green")
    assert _tokens("!!!") == ()


def test_tokens_match_on_word_prefixes_only() -> None:
    assert _has_prefix("dragon scimitar", "drag") is True
    assert _has_prefix("dragon scimitar", "scim") is True
    assert _has_prefix("dragon scimitar", "cimitar") is False


def test_an_artifact_from_another_schema_version_is_refused() -> None:
    from datetime import UTC, datetime

    import pytest

    from wiki_api.domain.manifest import Manifest

    manifest = Manifest.model_validate(
        {
            "data_version": "future",
            "schema_version": SCHEMA_VERSION + 1,
            "content_hash": "0" * 64,
            "built_at": datetime(2027, 1, 1, tzinfo=UTC),
            "game_version": "2009scape@ffffff",
        }
    )
    with pytest.raises(IncompatibleArtifact):
        InMemoryKnowledgeRepository(manifest)
