"""Shape the published description of this contract, which is itself a deliverable."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from fastapi.openapi.utils import get_openapi

from wiki_api.domain.attributes import AttributeFormat
from wiki_api.domain.identity import EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import AttributeGroup, RelationshipGroup, Unit

if TYPE_CHECKING:
    from collections.abc import Mapping

    from fastapi import FastAPI
    from starlette.routing import BaseRoute

TITLE: Final = "2009scape Wiki API"
VERSION: Final = "1.0.0"
KNOWN_VALUES: Final = "x-known-values"
SECURITY_SCHEME: Final = "issued_key"
UNGUARDED_PATHS: Final = frozenset({"/health"})
GUARD_NOTE: Final = (
    "Send the key you were issued as `Authorization: Bearer <token>`. Keys are "
    "handed out by whoever runs this deployment and do not expire; one that leaks is "
    "withdrawn by its holder's key id. A browser cannot keep one secret, so a public "
    "front end should call this through its own backend."
)
GUARD_RESPONSES: Final[dict[str, Any]] = {
    "401": {"description": "No key was sent, or it is not one this service answers."},
    "403": {"description": "Too many refused requests have come from this address."},
    "429": {
        "description": (
            "This key has asked for more than its share; `Retry-After` says when to "
            "come back."
        )
    },
}
OPEN_NOTE: Final = (
    "Published as an open string rather than a fixed enum, because new values get "
    "added as the data grows. The ones this build knows are listed under "
    "`x-known-values`. Treat anything else as a value you cannot render yet, not as "
    "an error."
)
DESCRIPTION: Final = """
A read-only HTTP API over the 2009scape game data: the things in the game, and the
links between them.

### What you get back

Ask for one entity and you get a page descriptor: the whole page described as data,
in a single response. Identity, an infobox, sections of attributes, and a first page
of every set of related entities. Each value arrives with its own label, group,
format, unit and `derived` flag, so one renderer can draw a type it has never seen.

Two habits keep a client working as the data grows:

* **Skip what you do not recognise.** A section carries a `render` word saying how it
  wants to be laid out. If the word is new to you, leave that section out instead of
  failing. The same goes for any value of an open vocabulary, which is documented
  with `x-known-values` in place of an enum.
* **Do not switch on field names.** Everything needed to display a value travels with
  the value, so your layout never has to know which fields a type has.

### Versions and caching

Every answer comes from one immutable build named by its data-version, and every
response repeats that version in the `X-Data-Version` header. A given data-version
always answers the same way, so you can cache hard. Add `?v=2026.07.30` to pin a
request to one build. If that build is no longer being served you get a 409 naming
the build that is, so recovering is one retry.

### Links

A link to another entity carries `type`, `id`, `slug` and `label`, and never a URL.
You build the address, so the same item can live at `/items/dragon-scimitar` on your
site and `/wiki/item/4587` on somebody else's.
"""

OPEN_VOCABULARIES: Final = (
    EntityType,
    RelationshipType,
    AttributeGroup,
    RelationshipGroup,
    AttributeFormat,
    Unit,
)

TAGS: Final[list[dict[str, Any]]] = [
    {
        "name": "entities",
        "description": (
            "Look up one thing you already know the name or the id of: its page, "
            "its hover card, one set of its neighbours, or what an old reference "
            "points at now."
        ),
    },
    {
        "name": "discovery",
        "description": (
            "Find something when you have no id yet. Browse everything of one "
            "type, search the full text, or ask which single entity a name means."
        ),
    },
    {
        "name": "meta",
        "description": (
            "About the server rather than the game: whether it can answer, and which "
            "build of the data it is answering from."
        ),
    },
]

_PARAMETRISED = re.compile(r"^(?P<outer>[A-Za-z0-9]+)_(?P<inner>[A-Za-z0-9_]+)_$")


def operation_id(route: BaseRoute) -> str:
    """Name the method a generated client gives this route."""
    return str(getattr(route, "name", ""))


def build(app: FastAPI, *, guarded: bool = False) -> dict[str, Any]:
    """Describe the whole contract, so a typed client falls out of it."""
    document = get_openapi(
        title=TITLE,
        version=VERSION,
        description=DESCRIPTION,
        routes=app.routes,
        tags=TAGS,
    )
    schemas = document.get("components", {}).get("schemas", {})
    _open_up(schemas)
    if guarded:
        _guarded(document)
    return _readable(document, _renames(schemas))


def _guarded(document: dict[str, Any]) -> None:
    """Declare that this deployment answers holders of an issued key.

    Said once here because the key is checked in one middleware, not route by route.
    """
    components = document.setdefault("components", {})
    components.setdefault("securitySchemes", {})[SECURITY_SCHEME] = {
        "type": "http",
        "scheme": "bearer",
        "description": GUARD_NOTE,
    }
    for path, served in document["paths"].items():
        if path in UNGUARDED_PATHS:
            continue
        for operation in served.values():
            operation["security"] = [{SECURITY_SCHEME: []}]
            operation.setdefault("responses", {}).update(GUARD_RESPONSES)


def _open_up(schemas: dict[str, Any]) -> None:
    for vocabulary in OPEN_VOCABULARIES:
        described = schemas.get(vocabulary.__name__)
        if described is None or "enum" not in described:
            continue
        known = list(described["enum"])
        described.clear()
        described.update(
            {
                "type": "string",
                "title": vocabulary.__name__,
                "description": f"{vocabulary.__doc__ or ''} {OPEN_NOTE}".strip(),
                KNOWN_VALUES: known,
                "examples": known[:1],
            }
        )


def _renames(schemas: Mapping[str, Any]) -> dict[str, str]:
    renamed: dict[str, str] = {}
    for name in schemas:
        matched = _PARAMETRISED.match(name)
        if matched is None:
            continue
        candidate = f"{matched['inner']}{matched['outer']}"
        if candidate not in schemas:
            renamed[name] = candidate
    return renamed


def _readable(document: dict[str, Any], renamed: Mapping[str, str]) -> dict[str, Any]:
    if not renamed:
        return document
    schemas = document["components"]["schemas"]
    document["components"]["schemas"] = {
        renamed.get(name, name): described for name, described in schemas.items()
    }
    retargeted: dict[str, Any] = _retarget(document, renamed)
    return retargeted


def _retarget(node: Any, renamed: Mapping[str, str]) -> Any:
    if isinstance(node, dict):
        return {
            name: _reference(value, renamed)
            if name == "$ref"
            else _retarget(value, renamed)
            for name, value in node.items()
        }
    if isinstance(node, list):
        return [_retarget(value, renamed) for value in node]
    return node


def _reference(value: Any, renamed: Mapping[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    head, _, name = value.rpartition("/")
    return f"{head}/{renamed[name]}" if name in renamed else value


# test cases


def test_a_page_is_named_after_whatever_it_holds() -> None:
    assert _renames({"Page_Row_": {}, "Row": {}}) == {"Page_Row_": "RowPage"}


def test_a_name_that_is_already_taken_is_left_alone() -> None:
    assert _renames({"Page_Row_": {}, "RowPage": {}}) == {}


def test_a_plain_name_is_never_rewritten() -> None:
    assert _renames({"Tooltip": {}, "PageDescriptor": {}}) == {}


def test_renaming_follows_every_pointer_at_the_old_name() -> None:
    document = {
        "components": {"schemas": {"Page_Row_": {"title": "Page[Row]"}}},
        "paths": {
            "/x": {"get": {"schema": {"$ref": "#/components/schemas/Page_Row_"}}}
        },
    }
    rewritten = _readable(document, {"Page_Row_": "RowPage"})
    assert "RowPage" in rewritten["components"]["schemas"]
    assert (
        rewritten["paths"]["/x"]["get"]["schema"]["$ref"]
        == "#/components/schemas/RowPage"
    )


def test_a_pointer_at_something_else_survives_untouched() -> None:
    document = {"a": {"$ref": "#/components/schemas/Tooltip"}}
    assert _retarget(document, {"Page_Row_": "RowPage"}) == document


def test_a_document_with_nothing_to_rename_is_left_exactly_as_it_was() -> None:
    document: dict[str, Any] = {"components": {"schemas": {"Tooltip": {}}}}
    assert _readable(document, {}) is document


def test_something_that_is_not_a_pointer_is_not_treated_as_one() -> None:
    assert _reference(7, {"Page_Row_": "RowPage"}) == 7


def test_a_growing_vocabulary_is_published_as_a_word_rather_than_a_choice() -> None:
    schemas = {EntityType.__name__: {"enum": ["item", "npc"], "type": "string"}}
    _open_up(schemas)
    described = schemas[EntityType.__name__]
    assert "enum" not in described
    assert described["type"] == "string"
    assert described[KNOWN_VALUES] == ["item", "npc"]


def test_the_words_a_vocabulary_holds_today_are_still_written_down() -> None:
    schemas = {EntityType.__name__: {"enum": ["item", "npc"], "type": "string"}}
    _open_up(schemas)
    assert OPEN_NOTE in schemas[EntityType.__name__]["description"]


def test_a_vocabulary_that_is_not_published_is_not_invented() -> None:
    schemas: dict[str, Any] = {}
    _open_up(schemas)
    assert schemas == {}


def test_a_closed_vocabulary_is_left_closed() -> None:
    from wiki_api.domain.presentation import GroupPlacement

    published = {vocabulary.__name__ for vocabulary in OPEN_VOCABULARIES}
    assert GroupPlacement.__name__ not in published


def _document() -> dict[str, Any]:
    return {
        "paths": {
            "/health": {"get": {"responses": {"200": {}}}},
            "/v1/about": {"get": {"responses": {"200": {}}}},
        },
        "components": {"schemas": {}},
    }


def test_an_unguarded_contract_says_nothing_about_keys() -> None:
    document = _document()
    assert "securitySchemes" not in document["components"]
    assert "security" not in document["paths"]["/v1/about"]["get"]


def test_a_guarded_contract_says_a_key_is_expected() -> None:
    document = _document()
    _guarded(document)
    scheme = document["components"]["securitySchemes"][SECURITY_SCHEME]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert document["paths"]["/v1/about"]["get"]["security"] == [{SECURITY_SCHEME: []}]


def test_a_health_check_is_never_declared_to_need_a_key() -> None:
    document = _document()
    _guarded(document)
    assert "security" not in document["paths"]["/health"]["get"]


def test_a_guarded_contract_documents_every_way_it_refuses() -> None:
    document = _document()
    _guarded(document)
    answered = document["paths"]["/v1/about"]["get"]["responses"]
    assert {"401", "403", "429"} <= set(answered)


def test_a_reader_is_warned_that_a_browser_cannot_hold_a_key() -> None:
    assert "browser cannot keep one secret" in GUARD_NOTE


def test_a_route_lends_its_name_to_the_method_a_client_generates() -> None:
    from fastapi.routing import APIRoute

    def read() -> None:
        return None

    assert operation_id(APIRoute("/x", read, name="entity")) == "entity"
