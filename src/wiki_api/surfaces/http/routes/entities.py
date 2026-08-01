"""Routes for one thing you can already name, addressed by its identity: each picks the
shape of the reference, asks the core one question, and lets the absence mapping shape a
non-answer.
"""

from __future__ import annotations

from functools import partial
from typing import Annotated, Any

from fastapi import APIRouter, Path, Response

from wiki_api.core import Block, Direction, Found, PageDescriptor, Tooltip
from wiki_api.domain.identity import EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.surfaces.http.absence import delivered
from wiki_api.surfaces.http.addressing import (
    ENTITIES_PREFIX,
    TOOLTIP_SEGMENT,
    WALK_SEGMENT,
    entity_path,
    reference,
    tooltip_path,
    walk_path,
)
from wiki_api.surfaces.http.caching import stamp_freshness
from wiki_api.surfaces.http.dependencies import (
    DirectionQuery,
    OffsetQuery,
    RowsDep,
    ServiceDep,
    SettingsDep,
)
from wiki_api.surfaces.http.schemas import ErrorBody, Present, Resolution

RESOLVE_SEGMENT = "resolve"

TypePath = Annotated[
    EntityType,
    Path(
        description=(
            "Which type of thing to look up, such as `item` or `npc`. "
            "`GET /v1/types` lists the types this build serves."
        )
    ),
]
RefPath = Annotated[
    str,
    Path(
        description=(
            "How to address the entity: its id (`4587`), its slug "
            "(`dragon-scimitar`), a slug it used to have, or the token the game "
            "source calls it by. A reference made only of digits is always an id."
        )
    ),
]
RelPath = Annotated[
    RelationshipType,
    Path(
        description=(
            "Which relationship to page through. `GET /v1/types` lists the "
            "relationships each type takes part in."
        )
    ),
]

ABSENT_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorBody,
        "description": (
            "Nothing published answers to that reference. The code says which "
            "case it is: `not_found` means there is no such entity, "
            "`not_published` means it exists in this build but is held back."
        ),
    },
    308: {
        "description": (
            "That reference is retired. `Location` holds the URL the same entity "
            "answers at now. Follow it, and store the new one."
        )
    },
}

router = APIRouter(prefix=ENTITIES_PREFIX, tags=["entities"])


@router.get(
    "/{entity_type}/{ref}",
    name="entity",
    summary="Get the whole page for one entity",
    response_description="The page, described as data and ready to render.",
    responses=ABSENT_RESPONSES,
)
def read_entity(
    entity_type: TypePath, ref: RefPath, service: ServiceDep
) -> PageDescriptor:
    """Get everything needed to draw one entity's page in a single response: identity,
    the infobox, the attribute sections, and a first page of every set of related
    entities.
    """
    return delivered(service.get_page(reference(entity_type, ref)), entity_path)


@router.get(
    f"/{{entity_type}}/{{ref}}/{TOOLTIP_SEGMENT}",
    name="tooltip",
    summary="Get the hover card for one entity",
    response_description="Just enough about the entity to fill a hover card.",
    responses=ABSENT_RESPONSES,
)
def read_tooltip(
    entity_type: TypePath,
    ref: RefPath,
    service: ServiceDep,
    settings: SettingsDep,
    response: Response,
) -> Tooltip:
    """Get identity, one sentence, and the few values the registry marks as worth
    showing on hover.
    """
    preview = delivered(service.tooltip(reference(entity_type, ref)), tooltip_path)
    stamp_freshness(response, settings.tooltip_cache_seconds)
    return preview


@router.get(
    f"/{{entity_type}}/{{ref}}/{WALK_SEGMENT}/{{rel}}",
    name="walk",
    summary="Page through one relationship of an entity",
    response_description="One page of related entities, plus the walk that made it.",
    responses=ABSENT_RESPONSES,
)
def read_walk(
    entity_type: TypePath,
    ref: RefPath,
    rel: RelPath,
    service: ServiceDep,
    limit: RowsDep,
    direction: DirectionQuery = Direction.FORWARD,
    offset: OffsetQuery = 0,
) -> Block:
    """Read one more page of a set of related entities that the entity page only
    started; `direction=reverse` reads the link the other way round.
    """
    answered = service.walk(
        reference(entity_type, ref), rel, direction, limit=limit, offset=offset
    )
    return delivered(answered, partial(walk_path, rel=rel))


@router.get(
    f"/{{entity_type}}/{{ref}}/{RESOLVE_SEGMENT}",
    name="resolve",
    summary="Check what a reference points at, without being sent there",
    response_description="What the reference resolves to, stated in the body.",
)
def read_resolution(
    entity_type: TypePath, ref: RefPath, service: ServiceDep
) -> Resolution:
    """Ask what a reference points at without being redirected there: live, retired,
    held back and unknown all come back as a 200 with an `outcome` in the body.
    """
    resolution = service.resolve(reference(entity_type, ref))
    if isinstance(resolution, Found):
        return Present(target=resolution.value.to_link())
    return resolution


# test cases


def _paths() -> set[str]:
    return {str(getattr(route, "path", "")) for route in router.routes}


def test_every_route_here_is_addressed_by_identity() -> None:
    assert all(path.startswith(ENTITIES_PREFIX) for path in _paths())


def test_the_relationship_is_a_parameter_rather_than_a_route_of_its_own() -> None:
    assert f"{ENTITIES_PREFIX}/{{entity_type}}/{{ref}}/rel/{{rel}}" in _paths()


def test_a_page_a_hover_and_an_inspection_are_separate_resources() -> None:
    base = f"{ENTITIES_PREFIX}/{{entity_type}}/{{ref}}"
    assert {base, f"{base}/tooltip", f"{base}/resolve"} <= _paths()


def test_every_route_names_itself_for_a_generated_client() -> None:
    named = {str(getattr(route, "name", "")) for route in router.routes}
    assert named == {"entity", "tooltip", "walk", "resolve"}


def test_absence_is_documented_wherever_a_thing_can_be_absent() -> None:
    assert set(ABSENT_RESPONSES) == {404, 308}
