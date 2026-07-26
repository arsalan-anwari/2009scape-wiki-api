"""The SQL a build writes with, kept in files rather than in strings here."""

from __future__ import annotations

from importlib import resources
from typing import Final

_PACKAGE: Final = "wiki_api.pipeline.artifact.sql"


def load(name: str) -> str:
    """Read one statement file out of the package."""
    return resources.files(_PACKAGE).joinpath(name).read_text(encoding="utf-8")


SCHEMA: Final = load("schema.sql")
INSERT_ENTITY: Final = load("insert_entity.sql")
INSERT_EDGE: Final = load("insert_edge.sql")
INSERT_ALIAS: Final = load("insert_alias.sql")
INSERT_PRICE: Final = load("insert_price.sql")
INSERT_META: Final = load("insert_meta.sql")
INSERT_SEARCH_ROW: Final = load("insert_search_row.sql")


# test cases


def test_every_statement_is_loaded_from_its_own_file() -> None:
    statements = (
        SCHEMA,
        INSERT_ENTITY,
        INSERT_EDGE,
        INSERT_ALIAS,
        INSERT_PRICE,
        INSERT_META,
        INSERT_SEARCH_ROW,
    )
    assert all(statement.strip() for statement in statements)


def test_the_schema_creates_every_table_the_artifact_needs() -> None:
    for table in ("meta", "entity", "entity_alias", "edge", "price_history"):
        assert f"CREATE TABLE {table}" in SCHEMA
    assert "CREATE VIRTUAL TABLE entity_fts USING fts5" in SCHEMA


def test_a_missing_statement_file_fails_loudly() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        load("no_such_statement.sql")
