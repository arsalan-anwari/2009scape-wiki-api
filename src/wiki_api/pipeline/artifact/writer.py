"""Write a snapshot out as the SQLite artifact."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import TYPE_CHECKING

from wiki_api.domain.attributes import computed_keys
from wiki_api.domain.entity import Entity, Visibility
from wiki_api.domain.manifest import SCHEMA_VERSION, Manifest
from wiki_api.pipeline.artifact import statements
from wiki_api.pipeline.artifact.hashing import content_hash

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from pydantic import BaseModel

    from wiki_api.domain.identity import EntityKey
    from wiki_api.domain.provenance import GameVersion
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

PAGE_SIZE = 4096


def write_artifact(
    snapshot: KnowledgeSnapshot,
    destination: Path,
    *,
    data_version: str,
    game_version: GameVersion | str,
    built_at: datetime,
) -> Manifest:
    """Write the snapshot to a fresh database and give back its manifest."""
    manifest = Manifest.model_validate(
        {
            "data_version": data_version,
            "schema_version": SCHEMA_VERSION,
            "content_hash": content_hash(snapshot),
            "built_at": built_at,
            "game_version": game_version,
        }
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    connection = sqlite3.connect(destination, isolation_level=None)
    try:
        connection.execute(f"PRAGMA page_size = {PAGE_SIZE}")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.executescript(statements.SCHEMA)
        connection.execute("BEGIN")
        _write_entities(connection, snapshot)
        _write_edges(connection, snapshot)
        _write_aliases(connection, snapshot)
        _write_prices(connection, snapshot)
        _write_meta(connection, manifest)
        connection.execute("COMMIT")
        connection.execute("VACUUM")
    finally:
        connection.close()
    return manifest


def _write_entities(
    connection: sqlite3.Connection, snapshot: KnowledgeSnapshot
) -> None:
    aliases = _aliases_by_entity(snapshot)
    for search_id, entity in enumerate(snapshot.entities, start=1):
        connection.execute(
            statements.INSERT_ENTITY,
            {
                "search_id": search_id,
                "type": entity.key.type.value,
                "id": entity.key.id,
                "slug": entity.slug,
                "name": entity.name,
                "description": entity.description,
                "source_key": entity.source_key,
                "canonical_id": entity.canonical_id,
                "variant_kind": (
                    entity.variant_kind.value if entity.variant_kind else None
                ),
                "searchable": int(entity.searchable),
                "visibility": entity.visibility.value,
                "hidden_reason": entity.hidden_reason,
                "icon_ref": entity.icon_ref,
                "attributes": _stored(entity.attributes),
                "source": entity.provenance.source.value,
                "source_file": entity.provenance.source_file,
                "source_ref": entity.provenance.source_ref,
                "game_version": str(entity.provenance.game_version),
            },
        )
        if _is_indexed(entity):
            connection.execute(
                statements.INSERT_SEARCH_ROW,
                {
                    "rowid": search_id,
                    "name": entity.name,
                    "aliases": " ".join(aliases[entity.key]),
                    "description": entity.description or "",
                },
            )


def _stored(attributes: BaseModel) -> str:
    """Pick what the artifact records: only what a source said, never a value the model
    works out for itself.
    """
    return attributes.model_dump_json(
        exclude_none=True, exclude=computed_keys(type(attributes))
    )


def _is_indexed(entity: Entity) -> bool:
    return entity.searchable and entity.visibility is Visibility.PUBLISHED


def _aliases_by_entity(snapshot: KnowledgeSnapshot) -> dict[EntityKey, list[str]]:
    grouped: defaultdict[EntityKey, list[str]] = defaultdict(list)
    for alias in snapshot.aliases:
        grouped[alias.key].append(alias.slug.replace("-", " "))
    return grouped


def _write_edges(connection: sqlite3.Connection, snapshot: KnowledgeSnapshot) -> None:
    for edge in snapshot.edges:
        connection.execute(
            statements.INSERT_EDGE,
            {
                "src_type": edge.src.type.value,
                "src_id": edge.src.id,
                "rel": edge.rel.value,
                "dst_type": edge.dst.type.value,
                "dst_id": edge.dst.id,
                "discriminator": edge.discriminator,
                "attributes": _stored(edge.attributes),
                "order_key": edge.order_key,
                "source": edge.provenance.source.value,
                "source_file": edge.provenance.source_file,
                "source_ref": edge.provenance.source_ref,
                "game_version": str(edge.provenance.game_version),
            },
        )


def _write_aliases(connection: sqlite3.Connection, snapshot: KnowledgeSnapshot) -> None:
    for alias in snapshot.aliases:
        connection.execute(
            statements.INSERT_ALIAS,
            {
                "type": alias.type.value,
                "alias_slug": alias.slug,
                "entity_id": alias.entity_id,
                "kind": alias.kind.value,
            },
        )


def _write_prices(connection: sqlite3.Connection, snapshot: KnowledgeSnapshot) -> None:
    for point in snapshot.prices:
        connection.execute(
            statements.INSERT_PRICE,
            {
                "item_id": point.item_id,
                "snapshot_date": point.snapshot_date.isoformat(),
                "value": point.value,
            },
        )


def _write_meta(connection: sqlite3.Connection, manifest: Manifest) -> None:
    rows = {
        "data_version": manifest.data_version,
        "schema_version": str(manifest.schema_version),
        "content_hash": manifest.content_hash,
        "built_at": manifest.built_at.isoformat(),
        "game_version": str(manifest.game_version),
    }
    for key in sorted(rows):
        connection.execute(statements.INSERT_META, {"key": key, "value": rows[key]})


# test cases


def _snapshot() -> KnowledgeSnapshot:
    from wiki_api.pipeline.artifact.merge import merge
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    document = {
        "schema": 1,
        "source": "fixture",
        "source_file": "item_configs.json",
        "game_version": "2009scape@test",
        "entities": [
            {"type": "item", "id": 4587, "name": "Dragon scimitar"},
            {
                "type": "item",
                "id": 4588,
                "name": "Dragon scimitar",
                "canonical_id": 4587,
                "variant_kind": "noted",
            },
            {"type": "npc", "id": 3089, "name": ""},
        ],
        "aliases": [{"type": "item", "slug": "dscim", "id": 4587}],
        "prices": [
            {"item_id": 4587, "snapshot_date": "2024-06-08", "value": 106049},
        ],
    }
    return merge(
        [OverlaySource.model_validate({"origin": "a.json", "document": document})]
    )


def _built(destination: Path) -> Manifest:
    from datetime import UTC, datetime

    return write_artifact(
        _snapshot(),
        destination,
        data_version="test",
        game_version="2009scape@test",
        built_at=datetime(2026, 7, 25, tzinfo=UTC),
    )


def test_provenance_keeps_the_kind_of_source_apart_from_the_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    _built(destination)
    connection = sqlite3.connect(destination)
    try:
        row = connection.execute(
            "SELECT source, source_file FROM entity WHERE id = 4587"
        ).fetchone()
    finally:
        connection.close()
    assert row == ("fixture", "item_configs.json")


def test_the_artifact_holds_every_entity(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    manifest = _built(destination)
    connection = sqlite3.connect(destination)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM entity").fetchone()
        assert rows[0] == 3
    finally:
        connection.close()
    assert manifest.schema_version == SCHEMA_VERSION


def test_only_searchable_entities_reach_the_search_index(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    _built(destination)
    connection = sqlite3.connect(destination)
    try:
        indexed = connection.execute("SELECT COUNT(*) FROM entity_fts").fetchone()
        assert indexed[0] == 1
    finally:
        connection.close()


def test_the_manifest_is_written_into_the_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    manifest = _built(destination)
    connection = sqlite3.connect(destination)
    try:
        rows = dict(connection.execute("SELECT key, value FROM meta").fetchall())
    finally:
        connection.close()
    assert rows["data_version"] == "test"
    assert rows["schema_version"] == str(SCHEMA_VERSION)
    assert rows["content_hash"] == manifest.content_hash
    assert rows["game_version"] == "2009scape@test"
    assert "game_commit" not in rows


def test_the_schema_rejects_a_value_outside_its_own_vocabulary(tmp_path: Path) -> None:
    import pytest

    destination = tmp_path / "knowledge.sqlite3"
    _built(destination)
    connection = sqlite3.connect(destination)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE entity SET type = 'banana' WHERE id = 4587")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE entity SET searchable = 7 WHERE id = 4587")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE price_history SET snapshot_date = 'soon'")
    finally:
        connection.close()


def test_the_schema_vocabularies_do_not_drift_from_the_domain() -> None:
    import re

    from wiki_api.domain.alias import AliasKind
    from wiki_api.domain.entity import VariantKind, Visibility
    from wiki_api.domain.identity import EntityType
    from wiki_api.domain.relationships import RelationshipType
    from wiki_api.domain.vocabulary import HiddenReason, SourceKind

    declared: dict[str, set[str]] = {}
    for column, values in re.findall(
        r"CHECK \((\w+) IN\s*\(([^)]*)\)\)", statements.SCHEMA
    ):
        members = set(re.findall(r"'([^']*)'", values))
        if members:
            declared.setdefault(column, set()).update(members)

    expected = {
        "type": EntityType,
        "src_type": EntityType,
        "dst_type": EntityType,
        "visibility": Visibility,
        "variant_kind": VariantKind,
        "hidden_reason": HiddenReason,
        "kind": AliasKind,
        "rel": RelationshipType,
        "source": SourceKind,
    }
    for column, vocabulary in expected.items():
        assert declared[column] == {member.value for member in vocabulary}, column


def test_aliases_are_indexed_alongside_the_name(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    _built(destination)
    connection = sqlite3.connect(destination)
    try:
        hit = connection.execute(
            "SELECT rowid FROM entity_fts WHERE entity_fts MATCH ?", ('"dscim"',)
        ).fetchone()
    finally:
        connection.close()
    assert hit is not None


def test_writing_twice_replaces_the_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    _built(destination)
    _built(destination)
    connection = sqlite3.connect(destination)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM entity").fetchone()
    finally:
        connection.close()
    assert rows[0] == 3
