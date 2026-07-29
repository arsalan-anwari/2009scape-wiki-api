"""The SQL the repository reads with, kept in files rather than in strings here."""

from __future__ import annotations

from importlib import resources
from typing import Final

from wiki_api.domain.page import SortOrder

_PACKAGE: Final = "wiki_api.repository.sqlite.sql"


def load(name: str) -> str:
    """Read one query file out of the package."""
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
COUNT_EDGES_FROM: Final = load("count_edges_from.sql")
COUNT_EDGES_TO: Final = load("count_edges_to.sql")
SELECT_VARIANTS: Final = load("select_variants.sql")
SELECT_PRICE_HISTORY: Final = load("select_price_history.sql")

LIST_BY_ORDER: Final[dict[SortOrder, str]] = {
    SortOrder.NAME: SELECT_ENTITIES_BY_NAME,
    SortOrder.ID: SELECT_ENTITIES_BY_ID,
}


# test cases


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
        COUNT_EDGES_FROM,
        COUNT_EDGES_TO,
        SELECT_VARIANTS,
        SELECT_PRICE_HISTORY,
    )
    for statement in statements:
        assert not any(word in statement.upper() for word in forbidden)


def test_every_walk_of_the_graph_is_bounded_and_countable() -> None:
    for statement in (SELECT_EDGES_FROM, SELECT_EDGES_TO):
        assert "LIMIT :limit" in statement
        assert "OFFSET :offset" in statement
    for statement in (COUNT_EDGES_FROM, COUNT_EDGES_TO):
        assert "COUNT(*) AS total" in statement


def test_a_walk_and_its_count_agree_on_which_edges_they_mean() -> None:
    pairs = (
        (SELECT_EDGES_FROM, COUNT_EDGES_FROM),
        (SELECT_EDGES_TO, COUNT_EDGES_TO),
    )
    for walk, counter in pairs:
        for clause in ("json_each(:keys)", ":include_hidden", "target.visibility"):
            assert clause in walk
            assert clause in counter


def test_a_walk_orders_by_enough_columns_to_be_unambiguous() -> None:
    for statement in (SELECT_EDGES_FROM, SELECT_EDGES_TO):
        ordering = statement.split("ORDER BY")[1]
        for column in ("rel", "order_key", "discriminator"):
            assert column in ordering
        assert "src_type" in ordering
        assert "dst_type" in ordering


def test_the_listing_queries_exclude_variants_and_unpublished_entities() -> None:
    for statement in (SELECT_ENTITIES_BY_NAME, SELECT_ENTITIES_BY_ID, COUNT_ENTITIES):
        assert "canonical_id IS NULL" in statement
        assert "visibility = :visibility" in statement


def test_a_missing_query_file_fails_loudly() -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        load("select_nothing.sql")
