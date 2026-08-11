"""Turn artifact rows back into domain objects."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, TypeVar

from pydantic import ValidationError

from wiki_api.domain.attributes import ATTRIBUTE_MODELS
from wiki_api.domain.entity import Entity, VariantKind, Visibility
from wiki_api.domain.errors import CorruptArtifact, IncompatibleArtifact
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
    from enum import StrEnum

_Member = TypeVar("_Member", bound="StrEnum")


def _named[Member: StrEnum](
    vocabulary: type[Member], table: str, column: str, value: object
) -> Member:
    """Read a stored value as a name the domain knows, raising a domain error rather
    than a bare ValueError.
    """
    try:
        return vocabulary(str(value))
    except ValueError as error:
        raise CorruptArtifact(table, column, value) from error


def entity_from_row(row: sqlite3.Row) -> Entity:
    """Read one entity out of the artifact."""
    entity_type = _named(EntityType, "entity", "type", row["type"])
    variant_kind = row["variant_kind"]
    try:
        attributes = ATTRIBUTE_MODELS[entity_type].model_validate_json(
            row["attributes"]
        )
    except ValidationError as error:
        raise CorruptArtifact("entity", "attributes", row["attributes"]) from error
    try:
        return Entity(
            key=EntityKey(type=entity_type, id=row["id"]),
            slug=row["slug"],
            name=row["name"],
            description=row["description"],
            source_key=row["source_key"],
            attributes=attributes,
            canonical_id=row["canonical_id"],
            variant_kind=(
                _named(VariantKind, "entity", "variant_kind", variant_kind)
                if variant_kind
                else None
            ),
            searchable=bool(row["searchable"]),
            visibility=_named(Visibility, "entity", "visibility", row["visibility"]),
            hidden_reason=row["hidden_reason"],
            icon_ref=row["icon_ref"],
            provenance=Provenance.model_validate(
                {
                    "source": row["source"],
                    "source_file": row["source_file"],
                    "source_ref": row["source_ref"],
                    "source_revision": row["source_revision"],
                    "game_version": row["game_version"],
                }
            ),
        )
    except ValidationError as error:
        raise CorruptArtifact("entity", "row", dict(row)) from error


def edge_from_row(row: sqlite3.Row) -> Edge:
    """Read one relationship out of the artifact."""
    rel = _named(RelationshipType, "edge", "rel", row["rel"])
    try:
        attributes = EDGE_ATTRIBUTE_MODELS[rel].model_validate_json(row["attributes"])
    except ValidationError as error:
        raise CorruptArtifact("edge", "attributes", row["attributes"]) from error
    try:
        return Edge(
            src=EntityKey(
                type=_named(EntityType, "edge", "src_type", row["src_type"]),
                id=row["src_id"],
            ),
            rel=rel,
            dst=EntityKey(
                type=_named(EntityType, "edge", "dst_type", row["dst_type"]),
                id=row["dst_id"],
            ),
            attributes=attributes,
            discriminator=row["discriminator"],
            order_key=row["order_key"],
            provenance=Provenance.model_validate(
                {
                    "source": row["source"],
                    "source_file": row["source_file"],
                    "source_ref": row["source_ref"],
                    "source_revision": row["source_revision"],
                    "game_version": row["game_version"],
                }
            ),
        )
    except ValidationError as error:
        raise CorruptArtifact("edge", "row", dict(row)) from error


def price_from_row(row: sqlite3.Row) -> PricePoint:
    """Read one price out of the artifact."""
    try:
        return PricePoint.model_validate(
            {
                "item_id": row["item_id"],
                "snapshot_date": row["snapshot_date"],
                "value": row["value"],
            }
        )
    except ValidationError as error:
        raise CorruptArtifact("price_history", "row", dict(row)) from error


def manifest_from_rows(rows: Iterable[sqlite3.Row]) -> Manifest:
    """Read what the artifact says about itself out of its meta table."""
    values = {row["key"]: row["value"] for row in rows}
    raw_version = values.get("schema_version")
    if raw_version is None or not raw_version.isdigit():
        raise IncompatibleArtifact(None, SCHEMA_VERSION)
    try:
        return Manifest.model_validate(
            {
                "data_version": values.get("data_version", ""),
                "schema_version": int(raw_version),
                "content_hash": values.get("content_hash", ""),
                "built_at": values.get("built_at", ""),
                "game_version": values.get("game_version", ""),
            }
        )
    except ValidationError as error:
        raise CorruptArtifact("meta", "row", values) from error


# test cases


def test_a_value_outside_the_vocabulary_reads_as_a_corrupt_artifact() -> None:
    import pytest

    row = _entity_row(type="banana")
    with pytest.raises(CorruptArtifact) as caught:
        entity_from_row(row)
    assert caught.value.column == "type"


def test_unreadable_attributes_read_as_a_corrupt_artifact() -> None:
    import pytest

    row = _entity_row(attributes='{"lifepoints": 240}')
    with pytest.raises(CorruptArtifact) as caught:
        entity_from_row(row)
    assert caught.value.column == "attributes"


def test_a_well_formed_row_still_reads_back_as_an_entity() -> None:
    entity = entity_from_row(_entity_row())
    assert entity.key == EntityKey(type=EntityType.ITEM, id=4587)
    assert entity.provenance.source_file == "item_configs.json"
    assert str(entity.provenance.game_version) == "2009scape@1f4a2c9"


def test_a_fact_answers_with_its_revision_without_the_staging_manifest() -> None:
    entity = entity_from_row(
        _entity_row(source="game_cache", source_revision="index 19 revision 214")
    )
    assert entity.provenance.source_revision == "index 19 revision 214"


def _entity_row(**overrides: object) -> sqlite3.Row:
    values: dict[str, object] = {
        "search_id": 1,
        "type": "item",
        "id": 4587,
        "slug": "dragon-scimitar",
        "name": "Dragon scimitar",
        "description": None,
        "source_key": None,
        "canonical_id": None,
        "variant_kind": None,
        "searchable": 1,
        "visibility": "published",
        "hidden_reason": None,
        "icon_ref": None,
        "attributes": "{}",
        "source": "game_config",
        "source_file": "item_configs.json",
        "source_ref": None,
        "source_revision": None,
        "game_version": "2009scape@1f4a2c9",
    }
    values.update(overrides)
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        columns = ", ".join(values)
        placeholders = ", ".join(f":{name}" for name in values)
        connection.execute(f"CREATE TABLE entity ({columns})")
        connection.execute(
            f"INSERT INTO entity ({columns}) VALUES ({placeholders})", values
        )
        row: sqlite3.Row = connection.execute("SELECT * FROM entity").fetchone()
        return row
    finally:
        connection.close()


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
