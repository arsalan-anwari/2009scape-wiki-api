"""The repository backed by the SQLite artifact."""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from wiki_api.domain.entity import Entity, Visibility
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
from wiki_api.domain.search import SearchHit
from wiki_api.repository.errors import ArtifactUnreadable
from wiki_api.repository.sqlite import queries
from wiki_api.repository.sqlite.connection import ReadOnlyConnections
from wiki_api.repository.sqlite.fts import to_match_query
from wiki_api.repository.sqlite.rows import (
    edge_from_row,
    entity_from_row,
    manifest_from_rows,
    price_from_row,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.prices import PricePoint
    from wiki_api.domain.relationships import RelationshipType


class SqliteKnowledgeRepository:
    """Reads the built artifact.

    Nothing above this class knows the storage is SQLite.
    """

    def __init__(self, path: Path) -> None:
        self._connections = ReadOnlyConnections(path)
        try:
            manifest = self._read_manifest()
        except sqlite3.DatabaseError as error:
            self._connections.close()
            raise ArtifactUnreadable(path, str(error)) from error
        except IncompatibleArtifact:
            self._connections.close()
            raise
        if not manifest.is_readable:
            self._connections.close()
            raise IncompatibleArtifact(manifest.schema_version, SCHEMA_VERSION)
        self._manifest = manifest

    def manifest(self) -> Manifest:
        return self._manifest

    def get_entity(self, key: EntityKey, *, include_hidden: bool = False) -> Entity:
        row = self._one(queries.SELECT_ENTITY, {"type": key.type.value, "id": key.id})
        if row is None:
            raise EntityNotFound(str(key))
        entity = entity_from_row(row)
        if not include_hidden and not entity.is_published:
            raise EntityHidden(key, entity.hidden_reason)
        return entity

    def get_entities(self, keys: Sequence[EntityKey]) -> Mapping[EntityKey, Entity]:
        if not keys:
            return {}
        rows = self._all(queries.SELECT_ENTITIES, {"keys": _as_json_keys(keys)})
        entities = [entity_from_row(row) for row in rows]
        return {entity.key: entity for entity in entities}

    def resolve_slug(self, entity_type: EntityType, slug: str) -> EntityKey:
        parameters = {"type": entity_type.value, "slug": slug}
        row = self._one(queries.SELECT_ENTITY_BY_SLUG, parameters)
        if row is not None:
            return EntityKey(type=entity_type, id=row["id"])
        alias = self._one(queries.SELECT_ALIAS, parameters)
        if alias is not None:
            raise EntityMoved(slug, EntityKey(type=entity_type, id=alias["entity_id"]))
        raise EntityNotFound(f"{entity_type.value}/{slug}")

    def resolve_source_key(self, entity_type: EntityType, source_key: str) -> EntityKey:
        row = self._one(
            queries.SELECT_ENTITY_BY_SOURCE_KEY,
            {"type": entity_type.value, "source_key": source_key},
        )
        if row is None:
            raise EntityNotFound(f"{entity_type.value}#{source_key}")
        return EntityKey(type=entity_type, id=row["id"])

    def list_entities(
        self,
        entity_type: EntityType,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order: SortOrder = SortOrder.NAME,
    ) -> Page[Entity]:
        parameters = {
            "type": entity_type.value,
            "visibility": Visibility.PUBLISHED.value,
            "limit": limit,
            "offset": offset,
        }
        rows = self._all(queries.LIST_BY_ORDER[order], parameters)
        total = self._total(queries.COUNT_ENTITIES, parameters)
        return Page[Entity](
            items=tuple(entity_from_row(row) for row in rows),
            total=total,
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
        match = to_match_query(query)
        if match is None:
            return Page[SearchHit](items=(), total=0, limit=limit, offset=offset)
        wanted = tuple(types) if types else tuple(EntityType)
        parameters = {
            "match": match,
            "types": json.dumps([entity_type.value for entity_type in wanted]),
            "limit": limit,
            "offset": offset,
        }
        rows = self._all(queries.SEARCH_ENTITIES, parameters)
        total = self._total(queries.COUNT_SEARCH_ENTITIES, parameters)
        hits = tuple(
            SearchHit(entity=entity_from_row(row), score=row["score"]) for row in rows
        )
        return Page[SearchHit](items=hits, total=total, limit=limit, offset=offset)

    def edges_from(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]:
        return self._edges(
            queries.SELECT_EDGES_FROM,
            queries.COUNT_EDGES_FROM,
            keys,
            rel,
            include_hidden,
            limit,
            offset,
        )

    def edges_to(
        self,
        keys: Sequence[EntityKey],
        *,
        rel: RelationshipType | None = None,
        include_hidden: bool = False,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[Edge]:
        return self._edges(
            queries.SELECT_EDGES_TO,
            queries.COUNT_EDGES_TO,
            keys,
            rel,
            include_hidden,
            limit,
            offset,
        )

    def variants_of(self, key: EntityKey) -> tuple[Entity, ...]:
        rows = self._all(
            queries.SELECT_VARIANTS, {"type": key.type.value, "id": key.id}
        )
        return tuple(entity_from_row(row) for row in rows)

    def price_history(
        self, item_id: int, *, since: date | None = None
    ) -> tuple[PricePoint, ...]:
        rows = self._all(
            queries.SELECT_PRICE_HISTORY,
            {"item_id": item_id, "since": since.isoformat() if since else None},
        )
        return tuple(price_from_row(row) for row in rows)

    def close(self) -> None:
        self._connections.close()

    def _edges(
        self,
        statement: str,
        counter: str,
        keys: Sequence[EntityKey],
        rel: RelationshipType | None,
        include_hidden: bool,
        limit: int,
        offset: int,
    ) -> Page[Edge]:
        parameters: dict[str, object] = {
            "keys": _as_json_keys(keys),
            "rel": rel.value if rel else None,
            "include_hidden": include_hidden,
            "hidden": Visibility.HIDDEN.value,
        }
        rows = self._all(statement, {**parameters, "limit": limit, "offset": offset})
        return Page[Edge](
            items=tuple(edge_from_row(row) for row in rows),
            total=self._total(counter, parameters),
            limit=limit,
            offset=offset,
        )

    def _read_manifest(self) -> Manifest:
        return manifest_from_rows(self._all(queries.SELECT_META, {}))

    def _one(
        self, statement: str, parameters: Mapping[str, object]
    ) -> sqlite3.Row | None:
        cursor = self._connections.get().execute(statement, parameters)
        try:
            row: sqlite3.Row | None = cursor.fetchone()
            return row
        finally:
            cursor.close()

    def _all(
        self, statement: str, parameters: Mapping[str, object]
    ) -> list[sqlite3.Row]:
        cursor = self._connections.get().execute(statement, parameters)
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    def _total(self, statement: str, parameters: Mapping[str, object]) -> int:
        row = self._one(statement, parameters)
        if row is None:
            return 0
        return int(row["total"])


def _as_json_keys(keys: Sequence[EntityKey]) -> str:
    """The keys a statement joins against, each one listed once.

    A repeated key would be joined more than once and would show its edges twice.
    """
    unique = dict.fromkeys(keys)
    return json.dumps(
        [{"type": key.type.value, "id": key.id} for key in unique],
        separators=(",", ":"),
    )


# test cases


def test_a_repeated_key_is_only_joined_once() -> None:
    scimitar = EntityKey(type=EntityType.ITEM, id=4587)
    noted = EntityKey(type=EntityType.ITEM, id=4588)
    assert _as_json_keys([scimitar, noted, scimitar]) == (
        '[{"type":"item","id":4587},{"type":"item","id":4588}]'
    )


def test_the_key_order_a_caller_asked_for_survives() -> None:
    noted = EntityKey(type=EntityType.ITEM, id=4588)
    scimitar = EntityKey(type=EntityType.ITEM, id=4587)
    assert _as_json_keys([noted, scimitar]).index("4588") < _as_json_keys(
        [noted, scimitar]
    ).index("4587")


def test_no_keys_serialise_to_an_empty_list() -> None:
    assert _as_json_keys([]) == "[]"
