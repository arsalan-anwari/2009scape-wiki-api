from __future__ import annotations

from importlib import resources
from typing import Final

from wiki_api.domain.page import SortOrder

_PACKAGE: Final = "wiki_api.repository.sqlite.sql"


def load(name: str) -> str:
    return resources.files(_PACKAGE).joinpath(name).read_text(encoding="utf-8")


SELECT_META: Final = load("select_meta.sql")
SELECT_ENTITY: Final = load("select_entity.sql")
SELECT_ENTITIES: Final = load("select_entities.sql")
SELECT_ENTITY_BY_SLUG: Final = load("select_entity_by_slug.sql")
SELECT_ENTITY_BY_SOURCE_KEY: Final = load("select_entity_by_source_key.sql")
SELECT_ALIAS: Final = load("select_alias.sql")
SELECT_ENTITIES_BY_NAME: Final = load("select_entities_by_name.sql")
SELECT_ENTITIES_BY_ID: Final = load("select_entities_by_id.sql")
COUNT_ENTITIES: Final = load("count_entities.sql")
SEARCH_ENTITIES: Final = load("search_entities.sql")
COUNT_SEARCH_ENTITIES: Final = load("count_search_entities.sql")
SELECT_EDGES_FROM: Final = load("select_edges_from.sql")
SELECT_EDGES_TO: Final = load("select_edges_to.sql")
SELECT_VARIANTS: Final = load("select_variants.sql")
SELECT_PRICE_HISTORY: Final = load("select_price_history.sql")

LIST_BY_ORDER: Final[dict[SortOrder, str]] = {
    SortOrder.NAME: SELECT_ENTITIES_BY_NAME,
    SortOrder.ID: SELECT_ENTITIES_BY_ID,
}


def test_every_sort_order_has_a_statement() -> None:
    for order in SortOrder:
        assert LIST_BY_ORDER[order].strip()


def test_no_query_writes_to_the_artifact() -> None:
    forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER")
    statements = (
        SELECT_META,
        SELECT_ENTITY,
        SELECT_ENTITIES,
        SELECT_ENTITY_BY_SLUG,
        SELECT_ENTITY_BY_SOURCE_KEY,
        SELECT_ALIAS,
        SELECT_ENTITIES_BY_NAME,
        SELECT_ENTITIES_BY_ID,
        COUNT_ENTITIES,
        SEARCH_ENTITIES,
        COUNT_SEARCH_ENTITIES,
        SELECT_EDGES_FROM,
        SELECT_EDGES_TO,
        SELECT_VARIANTS,
        SELECT_PRICE_HISTORY,
    )
    for statement in statements:
        assert not any(word in statement.upper() for word in forbidden)


def test_the_listing_queries_exclude_variants_and_unpublished_entities() -> None:
    for statement in (SELECT_ENTITIES_BY_NAME, SELECT_ENTITIES_BY_ID, COUNT_ENTITIES):
        assert "canonical_id IS NULL" in statement
        assert "visibility = :visibility" in statement


def test_a_missing_query_file_fails_loudly() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        load("select_nothing.sql")
