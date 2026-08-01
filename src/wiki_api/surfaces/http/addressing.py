"""Where things live in this api, and how a caller names one.

Paths are built here rather than inside a route so that a redirect can point at the same
resource the caller asked for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from wiki_api.domain.identity import EntityKey

if TYPE_CHECKING:
    from wiki_api.core import Reference
    from wiki_api.domain.identity import EntityType, Link
    from wiki_api.domain.relationships import RelationshipType

API_PREFIX: Final = "/v1"
ENTITIES_PREFIX: Final = f"{API_PREFIX}/entities"
TYPES_PREFIX: Final = f"{API_PREFIX}/types"
TOOLTIP_SEGMENT: Final = "tooltip"
WALK_SEGMENT: Final = "rel"


def reference(entity_type: EntityType, handle: str) -> Reference:
    """What the caller meant by the last segment of the path: a run of nothing but
    digits is an id, anything else a handle.
    """
    if handle.isdigit():
        return EntityKey(type=entity_type, id=int(handle))
    return (entity_type, handle)


def entity_path(link: Link) -> str:
    """Where the page of the thing this link points at is served."""
    return f"{ENTITIES_PREFIX}/{link.type.value}/{link.id}"


def tooltip_path(link: Link) -> str:
    """Where the hover sized answer for this link is served."""
    return f"{entity_path(link)}/{TOOLTIP_SEGMENT}"


def walk_path(link: Link, rel: RelationshipType) -> str:
    """Where one relationship of the thing this link points at is served."""
    return f"{entity_path(link)}/{WALK_SEGMENT}/{rel.value}"


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


def test_no_path_this_surface_builds_is_ever_an_absolute_url() -> None:
    from wiki_api.domain.relationships import RelationshipType as Rel

    built = (
        entity_path(_link()),
        tooltip_path(_link()),
        walk_path(_link(), Rel.LOCATED_IN),
    )
    assert all(path.startswith("/") for path in built)
    assert not any("://" in path for path in built)
