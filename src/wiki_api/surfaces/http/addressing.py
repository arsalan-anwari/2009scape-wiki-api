"""Build this api's paths, and read what a caller named.

Kept out of the routes so a redirect points at the same path the caller asked for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import urlencode

from wiki_api.domain.identity import EntityKey

if TYPE_CHECKING:
    from wiki_api.core import Reference
    from wiki_api.domain.identity import EntityType, Link
    from wiki_api.domain.relationships import RelationshipType

API_PREFIX: Final = "/v1"
ENTITIES_PREFIX: Final = f"{API_PREFIX}/entities"
TYPES_PREFIX: Final = f"{API_PREFIX}/types"
NEAR_NAMES_PREFIX: Final = f"{API_PREFIX}/near-names"
TOOLTIP_SEGMENT: Final = "tooltip"
WALK_SEGMENT: Final = "rel"
HISTORY_SEGMENT: Final = "prices"


def reference(entity_type: EntityType, handle: str) -> Reference:
    """Read the last path segment: all digits is an id, anything else a handle."""
    if handle.isdigit():
        return EntityKey(type=entity_type, id=int(handle))
    return (entity_type, handle)


def entity_path(link: Link) -> str:
    """Build the path serving this link's page."""
    return f"{ENTITIES_PREFIX}/{link.type.value}/{link.id}"


def tooltip_path(link: Link) -> str:
    """Build the path serving this link's hover-sized answer."""
    return f"{entity_path(link)}/{TOOLTIP_SEGMENT}"


def history_path(link: Link) -> str:
    """Address where this thing's week by week record is read."""
    return f"{entity_path(link)}/{HISTORY_SEGMENT}"


def walk_path(link: Link, rel: RelationshipType) -> str:
    """Build the path serving one of this link's relationships."""
    return f"{entity_path(link)}/{WALK_SEGMENT}/{rel.value}"


def near_names_path(entity_type: EntityType, name: str) -> str:
    """Build the path for asking what an unmatched name may have meant."""
    asked = urlencode({"name": name, "type": entity_type.value})
    return f"{NEAR_NAMES_PREFIX}?{asked}"


# test cases


def _link() -> Link:
    from wiki_api.domain.identity import EntityType as Type
    from wiki_api.domain.identity import Link as EntityLink

    return EntityLink(
        type=Type.ITEM, id=4587, slug="dragon-scimitar-4587", label="Dragon scimitar"
    )


def test_a_run_of_digits_is_an_identity() -> None:
    from wiki_api.domain.identity import EntityType as Type

    assert reference(Type.ITEM, "4587") == EntityKey(type=Type.ITEM, id=4587)


def test_anything_else_is_a_handle_the_core_has_to_look_up() -> None:
    from wiki_api.domain.identity import EntityType as Type

    assert reference(Type.ITEM, "dragon-scimitar-4587") == (
        Type.ITEM,
        "dragon-scimitar-4587",
    )


def test_a_page_is_addressed_by_identity_so_a_rename_cannot_break_it() -> None:
    assert entity_path(_link()) == "/v1/entities/item/4587"


def test_a_hover_hangs_off_the_page_it_previews() -> None:
    assert tooltip_path(_link()) == "/v1/entities/item/4587/tooltip"


def test_one_relationship_is_a_resource_of_its_own() -> None:
    from wiki_api.domain.relationships import RelationshipType as Rel

    path = walk_path(_link(), Rel.LOCATED_IN)
    assert path == "/v1/entities/item/4587/rel/located_in"


def test_a_name_that_meant_nothing_is_pointed_at_the_names_that_exist() -> None:
    from wiki_api.domain.identity import EntityType as Type

    assert near_names_path(Type.ITEM, "dragon scimtar") == (
        "/v1/near-names?name=dragon+scimtar&type=item"
    )


def test_a_name_full_of_punctuation_is_still_safe_to_point_at() -> None:
    from wiki_api.domain.identity import EntityType as Type

    assert near_names_path(Type.ITEM, "a&b=c") == (
        "/v1/near-names?name=a%26b%3Dc&type=item"
    )


def test_no_path_this_surface_builds_is_ever_an_absolute_url() -> None:
    from wiki_api.domain.identity import EntityType as Type
    from wiki_api.domain.relationships import RelationshipType as Rel

    built = (
        entity_path(_link()),
        tooltip_path(_link()),
        walk_path(_link(), Rel.LOCATED_IN),
        near_names_path(Type.ITEM, "dragon"),
    )
    assert all(path.startswith("/") for path in built)
    assert not any("://" in path for path in built)
