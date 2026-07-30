"""What this process is, as opposed to what it knows.

Neither answer is about the game, so neither is held by a cache: one says whether this
process can serve at all, and the other says exactly which build it is serving, which
is what a consumer keys its own caching on.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from wiki_api.domain.manifest import Manifest
from wiki_api.surfaces.http.addressing import API_PREFIX
from wiki_api.surfaces.http.caching import decline_caching
from wiki_api.surfaces.http.dependencies import ManifestDep
from wiki_api.surfaces.http.schemas import Health

HEALTH_PATH = "/health"

router = APIRouter(tags=["meta"])


@router.get(
    HEALTH_PATH,
    name="health",
    summary="Check whether this server can answer",
    response_description="The server is up and has data open.",
)
def read_health(manifest: ManifestDep, response: Response) -> Health:
    """Say that the server is up and has a readable build of the data open.

    A process that failed to open its data never answers here at all, so a reply
    from this route means it can really serve. Point a load balancer or a container
    probe at it. Never cached.
    """
    decline_caching(response)
    return Health(
        data_version=manifest.data_version, schema_version=manifest.schema_version
    )


@router.get(
    f"{API_PREFIX}/about",
    name="about",
    summary="Find out which build of the data is being served",
    response_description="The manifest of the build currently being served.",
)
def read_about(manifest: ManifestDep, response: Response) -> Manifest:
    """Describe the build that every other answer comes from.

    `data_version` is what every response repeats in the `X-Data-Version` header,
    what to use as a cache key, and what `?v=` pins to. `game_version` records the
    state of the game it was built from. Never cached itself, because this is how
    you notice the build has changed.
    """
    decline_caching(response)
    return manifest


# test cases


def _paths() -> set[str]:
    return {str(getattr(route, "path", "")) for route in router.routes}


def test_a_health_check_is_not_part_of_the_versioned_contract() -> None:
    assert HEALTH_PATH in _paths()
    assert not HEALTH_PATH.startswith(API_PREFIX)


def test_which_build_is_served_is_part_of_the_versioned_contract() -> None:
    assert f"{API_PREFIX}/about" in _paths()


def test_every_route_names_itself_for_a_generated_client() -> None:
    named = {str(getattr(route, "name", "")) for route in router.routes}
    assert named == {"health", "about"}
