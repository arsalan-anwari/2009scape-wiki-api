from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from wiki_api.domain.attributes import ATTRIBUTE_MODELS
from wiki_api.domain.entity import Entity, VariantKind, Visibility
from wiki_api.domain.errors import IncompatibleArtifact
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.manifest import SCHEMA_VERSION, Manifest
from wiki_api.domain.prices import PricePoint
from wiki_api.domain.provenance import Provenance
from wiki_api.domain.relationships import (
    EDGE_ATTRIBUTE_MODELS,
    Edge,
    RelationshipType,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


def entity_from_row(row: sqlite3.Row) -> Entity:
    entity_type = EntityType(row["type"])
    attributes = ATTRIBUTE_MODELS[entity_type].model_validate_json(row["attributes"])
    variant_kind = row["variant_kind"]
    return Entity(
        key=EntityKey(type=entity_type, id=row["id"]),
        slug=row["slug"],
        name=row["name"],
        description=row["description"],
        source_key=row["source_key"],
        attributes=attributes,
        canonical_id=row["canonical_id"],
        variant_kind=VariantKind(variant_kind) if variant_kind else None,
        searchable=bool(row["searchable"]),
        visibility=Visibility(row["visibility"]),
        hidden_reason=row["hidden_reason"],
        icon_ref=row["icon_ref"],
        provenance=Provenance(
            source=row["source"],
            game_version=row["game_version"],
            source_ref=row["source_ref"],
        ),
    )


def edge_from_row(row: sqlite3.Row) -> Edge:
    rel = RelationshipType(row["rel"])
    attributes = EDGE_ATTRIBUTE_MODELS[rel].model_validate_json(row["attributes"])
    return Edge(
        src=EntityKey(type=EntityType(row["src_type"]), id=row["src_id"]),
        rel=rel,
        dst=EntityKey(type=EntityType(row["dst_type"]), id=row["dst_id"]),
        attributes=attributes,
        discriminator=row["discriminator"],
        order_key=row["order_key"],
        provenance=Provenance(
            source=row["source"],
            game_version=row["game_version"],
            source_ref=row["source_ref"],
        ),
    )


def price_from_row(row: sqlite3.Row) -> PricePoint:
    return PricePoint.model_validate(
        {
            "item_id": row["item_id"],
            "snapshot_date": row["snapshot_date"],
            "value": row["value"],
        }
    )


def manifest_from_rows(rows: Iterable[sqlite3.Row]) -> Manifest:
    values = {row["key"]: row["value"] for row in rows}
    raw_version = values.get("schema_version")
    if raw_version is None or not raw_version.isdigit():
        raise IncompatibleArtifact(None, SCHEMA_VERSION)
    return Manifest.model_validate(
        {
            "data_version": values.get("data_version", ""),
            "schema_version": int(raw_version),
            "content_hash": values.get("content_hash", ""),
            "built_at": values.get("built_at", ""),
            "game_version": values.get("game_version", ""),
            "game_commit": values.get("game_commit"),
        }
    )


def test_an_artifact_without_a_schema_version_is_rejected() -> None:
    import pytest

    with pytest.raises(IncompatibleArtifact):
        manifest_from_rows(_meta_rows({"data_version": "test"}))


def test_a_non_numeric_schema_version_is_rejected() -> None:
    import pytest

    with pytest.raises(IncompatibleArtifact):
        manifest_from_rows(_meta_rows({"schema_version": "one"}))


def test_the_manifest_is_read_back_from_the_meta_table() -> None:
    manifest = manifest_from_rows(
        _meta_rows(
            {
                "data_version": "2026.07.25",
                "schema_version": str(SCHEMA_VERSION),
                "content_hash": "0" * 64,
                "built_at": "2026-07-25T00:00:00+00:00",
                "game_version": "2009scape@5a37f2f8",
                "game_commit": "5a37f2f8",
            }
        )
    )
    assert manifest.is_readable is True
    assert manifest.game_commit == "5a37f2f8"


def _meta_rows(values: dict[str, str]) -> list[sqlite3.Row]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        connection.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)", list(values.items())
        )
        return connection.execute("SELECT key, value FROM meta").fetchall()
    finally:
        connection.close()
