"""Find things without already knowing which one you mean: an index, a search, a best
guess, and the registry a generic front end reads.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Path, Query

from wiki_api.core import Compared, EntitySummary, Match, SearchResult, TypeInfo
from wiki_api.core.results import Uncomparable
from wiki_api.domain.identity import EntityType
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page, SortOrder
from wiki_api.domain.query import Comparison
from wiki_api.surfaces.http.addressing import (
    API_PREFIX,
    NEAR_NAMES_PREFIX,
    TYPES_PREFIX,
)
from wiki_api.surfaces.http.dependencies import (
    ComparisonQuery,
    DescendingQuery,
    HoldsQuery,
    LimitQuery,
    NearLimitsDep,
    NumberQuery,
    OffsetQuery,
    OrderedByQuery,
    OrderQuery,
    ServiceDep,
    TypesQuery,
)
from wiki_api.surfaces.http.errors import ContractError
from wiki_api.surfaces.http.schemas import ErrorBody, ErrorCode

UNCOMPARABLE_MESSAGE = (
    "nothing that type declares answers to those words; GET /v1/types publishes "
    "what each one declares"
)

TypePath = Annotated[
    EntityType,
    Path(
        description=(
            "Which type of thing to list, such as `item` or `quest`. "
            "`GET /v1/types` lists the types this build serves."
        )
    ),
]
TermQuery = Annotated[
    str,
    Query(
        description=(
            "What to search for, typed the way a reader would type it. Every word "
            "is matched as a prefix and all of them have to match, so `drag scim` "
            "finds the dragon scimitar. There is no query syntax: quotes, brackets "
            "and words like `OR` count as ordinary text."
        )
    ),
]
NameQuery = Annotated[
    str,
    Query(
        description=(
            "The full name of the single thing you mean, such as `Dragon scimitar`."
        )
    ),
]
MisspeltQuery = Annotated[
    str,
    Query(
        description=(
            "The name that answered to nothing, exactly as it was typed, such as "
            "`dragon scimtar`."
        )
    ),
]
OneTypeQuery = Annotated[
    EntityType,
    Query(
        alias="type",
        description=(
            "Which sort of thing the name belongs to. Required: `dagon scimitar` "
            "and `dagon` are near misses for different things depending on whether "
            "an item or an npc was meant, so this question cannot be answered "
            "without it. `GET /v1/types` lists the sorts this build serves."
        ),
    ),
]

router = APIRouter(prefix=API_PREFIX, tags=["discovery"])


@router.get(
    "/types",
    name="types",
    summary="List every entity type and how its fields are presented",
    response_description="Every type served, with its attributes and relationships.",
)
def read_types(service: ServiceDep) -> list[TypeInfo]:
    """List every type with its attributes and its relationships, labelled for reading
    each way round.
    """
    return list(service.describe_types())


@router.get(
    "/types/{entity_type}/entities",
    name="listing",
    summary="List all entities of one type, a page at a time",
    response_description="One page of the index for that type.",
)
def read_listing(
    entity_type: TypePath,
    service: ServiceDep,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
    offset: OffsetQuery = 0,
    order: OrderQuery = SortOrder.NAME,
) -> Page[EntitySummary]:
    """List every published entity of one type, sorted and paged, leaving out
    variants.
    """
    return service.list_type(entity_type, limit=limit, offset=offset, order=order)


@router.get(
    "/types/{entity_type}/compare",
    name="compare",
    summary="List the entities of one type whose stored number answers a question",
    response_description=(
        "One page of entities, each carrying the values the question was about."
    ),
    responses={
        422: {
            "model": ErrorBody,
            "description": (
                "Nothing declared for that type answers to those words. "
                "`GET /v1/types` publishes what each type declares, and anything "
                "there formatted as a number can be compared."
            ),
        }
    },
)
def read_comparison(
    entity_type: TypePath,
    service: ServiceDep,
    holds: HoldsQuery = None,
    how: ComparisonQuery = Comparison.AT_LEAST,
    number: NumberQuery = 0.0,
    ordered_by: OrderedByQuery = None,
    descending: DescendingQuery = False,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
    offset: OffsetQuery = 0,
) -> Compared:
    """List the entities of one type picked out by a number they store, paged and
    ordered.

    Anything not carrying a value being compared or sorted on is left out of the
    answer and out of the total.
    """
    answered = service.compare(
        entity_type,
        holds=holds,
        how=how,
        number=number,
        ordered_by=ordered_by,
        descending=descending,
        limit=limit,
        offset=offset,
    )
    if isinstance(answered, Uncomparable):
        raise ContractError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            ErrorCode.INVALID_REQUEST,
            UNCOMPARABLE_MESSAGE,
        )
    return answered.value


@router.get(
    "/search",
    name="search",
    summary="Search the full text across every type",
    response_description="One page of matches, best first.",
)
def read_search(
    service: ServiceDep,
    q: TermQuery,
    types: TypesQuery = None,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
    offset: OffsetQuery = 0,
) -> Page[SearchResult]:
    """Search names, alternative names and descriptions across every type, best first
    with a score.
    """
    return service.search(q, types=types, limit=limit, offset=offset)


@router.get(
    "/find",
    name="find",
    summary="Look up the one entity that goes by this name",
    response_description="The single best match, if there is one, plus the runners-up.",
)
def read_find(
    service: ServiceDep,
    name: NameQuery,
    types: TypesQuery = None,
    limit: LimitQuery = DEFAULT_PAGE_SIZE,
) -> Match:
    """Turn a name into the one entity it means, with the ranked runners-up.

    `best_match` is null only when nothing matched at all.
    """
    return service.find(name, types=types, limit=limit)


@router.get(
    "/near-names",
    name="near_names",
    summary="Ask which real names a misspelt one might have meant",
    response_description=(
        "The closest names that exist, best first, or nothing at all when none of "
        "them is close enough to be worth offering."
    ),
)
def read_near_names(
    service: ServiceDep,
    name: MisspeltQuery,
    entity_type: OneTypeQuery,
    near: NearLimitsDep,
) -> Page[SearchResult]:
    """Turn an unmatched name into the real names it may have meant, each carrying
    identity and nothing else.

    An empty answer means nothing was close, which is an answer rather than a failure.
    """
    return service.near_names(
        name,
        entity_type,
        limit=near.limit,
        keep=near.keep,
        floor=near.floor,
    )


# test cases


def _paths() -> set[str]:
    return {str(getattr(route, "path", "")) for route in router.routes}


def test_an_index_hangs_off_the_type_it_indexes() -> None:
    assert f"{TYPES_PREFIX}/{{entity_type}}/entities" in _paths()


def test_searching_and_meaning_one_thing_are_different_resources() -> None:
    assert {f"{API_PREFIX}/search", f"{API_PREFIX}/find"} <= _paths()


def test_asking_what_a_misspelling_meant_is_a_resource_of_its_own() -> None:
    assert NEAR_NAMES_PREFIX in _paths()


def test_the_sort_of_thing_is_required_before_a_near_name_is_guessed_at() -> None:
    from typing import get_args

    _, declared = get_args(OneTypeQuery)
    assert declared.alias == "type"
    assert declared.is_required()


def test_the_registries_are_published_under_a_name_of_their_own() -> None:
    assert TYPES_PREFIX in _paths()


def test_every_route_names_itself_for_a_generated_client() -> None:
    named = {str(getattr(route, "name", "")) for route in router.routes}
    assert named == {
        "types",
        "listing",
        "compare",
        "search",
        "find",
        "near_names",
    }


def test_comparing_hangs_off_the_type_whose_values_are_compared() -> None:
    assert f"{TYPES_PREFIX}/{{entity_type}}/compare" in _paths()


def test_a_caller_naming_no_value_at_all_is_refused_rather_than_listed() -> None:
    from typing import get_args

    for alias in (HoldsQuery, OrderedByQuery):
        _, declared = get_args(alias)
        assert declared.description
