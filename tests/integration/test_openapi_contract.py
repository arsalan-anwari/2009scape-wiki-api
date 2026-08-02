from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from wiki_api.surfaces.http import create_app
from wiki_api.surfaces.http.openapi import KNOWN_VALUES, OPEN_VOCABULARIES

if TYPE_CHECKING:
    from wiki_api.config import Settings

SNAPSHOT = Path(__file__).parent.parent / "fixtures" / "openapi.json"

CLOSED_VOCABULARIES = ("GroupPlacement", "Direction", "SortOrder")


@pytest.fixture
def document(http_settings: Settings) -> dict[str, Any]:
    published: dict[str, Any] = create_app(http_settings).openapi()
    return published


def _schemas(document: dict[str, Any]) -> dict[str, Any]:
    described: dict[str, Any] = document["components"]["schemas"]
    return described


def _operations(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        operation
        for served in document["paths"].values()
        for operation in served.values()
    ]


def test_the_published_contract_is_the_one_that_was_reviewed(
    document: dict[str, Any],
) -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert document == expected


def test_every_question_the_contract_answers_has_a_route(
    document: dict[str, Any],
) -> None:
    assert set(document["paths"]) == {
        "/health",
        "/v1/about",
        "/v1/types",
        "/v1/types/{entity_type}/entities",
        "/v1/search",
        "/v1/find",
        "/v1/near-names",
        "/v1/entities/{entity_type}/{ref}",
        "/v1/entities/{entity_type}/{ref}/tooltip",
        "/v1/entities/{entity_type}/{ref}/rel/{rel}",
        "/v1/entities/{entity_type}/{ref}/resolve",
    }


def test_nothing_but_reading_is_published(document: dict[str, Any]) -> None:
    methods = {method for served in document["paths"].values() for method in served}
    assert methods == {"get"}


def test_a_vocabulary_that_grows_is_published_as_a_word(
    document: dict[str, Any],
) -> None:
    schemas = _schemas(document)
    for vocabulary in OPEN_VOCABULARIES:
        described = schemas[vocabulary.__name__]
        assert described["type"] == "string"
        assert "enum" not in described
        assert described[KNOWN_VALUES]


def test_the_words_a_vocabulary_holds_today_are_still_written_down(
    document: dict[str, Any],
) -> None:
    known = set(_schemas(document)["EntityType"][KNOWN_VALUES])
    assert known == {"item", "npc", "shop", "quest", "location"}


def test_a_vocabulary_that_cannot_grow_stays_a_closed_choice(
    document: dict[str, Any],
) -> None:
    schemas = _schemas(document)
    for name in CLOSED_VOCABULARIES:
        assert schemas[name]["enum"]


def test_a_page_of_something_is_named_after_what_it_holds(
    document: dict[str, Any],
) -> None:
    schemas = _schemas(document)
    assert {"RowPage", "SearchResultPage", "EntitySummaryPage"} <= set(schemas)
    assert not [name for name in schemas if name.endswith("_")]


def test_a_page_on_the_wire_carries_its_own_cursor(
    document: dict[str, Any],
) -> None:
    held = _schemas(document)["RowPage"]["properties"]
    assert {"items", "total", "limit", "offset", "has_more", "next_offset"} <= set(held)


def test_a_section_publishes_the_word_that_says_how_to_lay_it_out(
    document: dict[str, Any],
) -> None:
    described = _schemas(document)["Section"]["properties"]["render"]
    assert described["default"] == "attributes"


def test_every_method_a_client_generates_is_named_by_hand(
    document: dict[str, Any],
) -> None:
    named = [operation["operationId"] for operation in _operations(document)]
    assert sorted(named) == sorted(set(named))
    assert set(named) == {
        "health",
        "about",
        "types",
        "listing",
        "search",
        "find",
        "near_names",
        "entity",
        "tooltip",
        "walk",
        "resolve",
    }


def test_every_route_says_what_it_is_for(document: dict[str, Any]) -> None:
    for operation in _operations(document):
        assert operation["summary"]
        assert operation["description"]
        assert operation["tags"]


def test_absence_is_documented_wherever_a_thing_can_be_absent(
    document: dict[str, Any],
) -> None:
    for path, served in document["paths"].items():
        if not path.startswith("/v1/entities") or path.endswith("resolve"):
            continue
        answered = served["get"]["responses"]
        assert "404" in answered
        assert "308" in answered


def test_a_failure_is_described_in_one_shape(document: dict[str, Any]) -> None:
    body = _schemas(document)["ErrorBody"]
    detail = _schemas(document)["ErrorDetail"]
    assert set(body["properties"]) == {"error"}
    assert set(detail["properties"]) == {
        "code",
        "message",
        "data_version",
        "near_names",
    }
    assert set(detail["required"]) == {"code", "message"}


def test_the_contract_tells_a_reader_to_ignore_what_it_does_not_know(
    document: dict[str, Any],
) -> None:
    published = document["info"]["description"]
    assert "render" in published
    assert KNOWN_VALUES in published
    assert "recognise" in published


def test_the_contract_never_hands_a_consumer_a_url(
    document: dict[str, Any],
) -> None:
    assert "url" not in _schemas(document)["Link"]["properties"]


def test_every_bounded_parameter_explains_itself(document: dict[str, Any]) -> None:
    for operation in _operations(document):
        for parameter in operation.get("parameters", ()):
            assert parameter.get("description"), parameter["name"]
