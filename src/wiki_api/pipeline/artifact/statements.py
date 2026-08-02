"""Load the SQL a build writes with, kept in files rather than in strings."""

from __future__ import annotations

import re
from importlib import resources
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

_PACKAGE: Final = "wiki_api.pipeline.artifact.sql"

_VOCABULARY_CHECK: Final = re.compile(
    r"CHECK\s*\(\s*(\w+)\s+IN\s*\(([^)]*)\)\s*\)", re.IGNORECASE
)
_QUOTED: Final = re.compile(r"'([^']*)'")


def load(name: str) -> str:
    """Read one statement file out of the package."""
    return resources.files(_PACKAGE).joinpath(name).read_text(encoding="utf-8")


def declared_vocabularies(schema: str) -> Mapping[str, frozenset[str]]:
    """Read the values each schema column accepts, which must stay identical to the
    vocabularies the domain declares.
    """
    declared: dict[str, frozenset[str]] = {}
    for column, listed in _VOCABULARY_CHECK.findall(schema):
        values = frozenset(_QUOTED.findall(listed))
        if not values:
            continue
        declared[column] = declared.get(column, frozenset()) | values
    return declared


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


def test_the_schema_states_the_same_vocabularies_the_domain_declares() -> None:
    from enum import StrEnum

    from wiki_api.domain.alias import AliasKind
    from wiki_api.domain.entity import VariantKind, Visibility
    from wiki_api.domain.identity import EntityType
    from wiki_api.domain.relationships import RelationshipType
    from wiki_api.domain.vocabulary import HiddenReason, SourceKind

    expected: dict[str, type[StrEnum]] = {
        "type": EntityType,
        "src_type": EntityType,
        "dst_type": EntityType,
        "rel": RelationshipType,
        "variant_kind": VariantKind,
        "visibility": Visibility,
        "hidden_reason": HiddenReason,
        "source": SourceKind,
        "kind": AliasKind,
    }
    declared = declared_vocabularies(SCHEMA)
    assert set(declared) == set(expected)
    for column, vocabulary in expected.items():
        assert declared[column] == {member.value for member in vocabulary}


def test_a_column_the_schema_constrains_by_hand_is_read_back() -> None:
    declared = declared_vocabularies(
        "CREATE TABLE t (colour TEXT CHECK (colour IN ('red', 'blue')))"
    )
    assert declared == {"colour": frozenset({"red", "blue"})}


def test_a_check_that_names_no_vocabulary_is_ignored() -> None:
    listed = "searchable INTEGER CHECK (searchable IN (0, 1))"
    assert declared_vocabularies(listed) == {}
