"""Hand a route the repository, reached through the provider per request, and the
query parameters every listing shares.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Query
from starlette.requests import Request

from wiki_api.config import Settings
from wiki_api.core import Direction, KnowledgeService
from wiki_api.domain.identity import EntityType
from wiki_api.domain.manifest import Manifest
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SortOrder
from wiki_api.domain.search import MOST_NEAR_LIMIT
from wiki_api.repository.provider import RepositoryProvider

PROVIDER_STATE = "provider"
SETTINGS_STATE = "settings"


def provider_of(request: Request) -> RepositoryProvider:
    """Read the provider this application was started with."""
    return cast(RepositoryProvider, getattr(request.app.state, PROVIDER_STATE))


def settings_of(request: Request) -> Settings:
    """Read the settings this application was started with."""
    return cast(Settings, getattr(request.app.state, SETTINGS_STATE))


def service_of(request: Request) -> KnowledgeService:
    """Open a service over whatever is being served now, at the settings' page size."""
    return KnowledgeService(
        provider_of(request).current(), block_size=settings_of(request).block_rows
    )


def manifest_of(request: Request) -> Manifest:
    """Read what the artifact being served says about itself."""
    return provider_of(request).current().manifest()


ServiceDep = Annotated[KnowledgeService, Depends(service_of)]
SettingsDep = Annotated[Settings, Depends(settings_of)]
ManifestDep = Annotated[Manifest, Depends(manifest_of)]

LimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_PAGE_SIZE,
        description=(
            "How many results one page holds. The response repeats the limit it "
            "used, so you never have to assume."
        ),
    ),
]
OffsetQuery = Annotated[
    int,
    Query(
        ge=0,
        description=(
            "How many results to skip before this page. To read the next page, "
            "pass back the `next_offset` from the last response. It is null once "
            "you have reached the end."
        ),
    ),
]
TypesQuery = Annotated[
    list[EntityType] | None,
    Query(
        alias="type",
        description=(
            "Limit the answer to certain types of thing. Repeat the parameter for "
            "more than one, as in `?type=item&type=npc`. Leave it off to cover "
            "every type."
        ),
    ),
]
OrderQuery = Annotated[
    SortOrder,
    Query(
        description=(
            "How to sort the listing: `name` for alphabetical, `id` for the game's "
            "own numbering."
        )
    ),
]
DirectionQuery = Annotated[
    Direction,
    Query(
        description=(
            "Which way to read the relationship. `forward` for what this entity "
            "points at, `reverse` for what points at it."
        )
    ),
]
RowsQuery = Annotated[
    int | None,
    Query(
        ge=1,
        le=MAX_PAGE_SIZE,
        description=(
            "How many rows this page holds. Defaults to the width a whole entity "
            "page uses for the same relationship, so continuing a list is never "
            "narrower than the list you are continuing."
        ),
    ),
]


def rows_of(request: Request, limit: RowsQuery = None) -> int:
    """Read how many rows a relationship page holds, defaulting to the entity page's
    width.
    """
    return limit if limit is not None else settings_of(request).block_rows


RowsDep = Annotated[int, Depends(rows_of)]

NearLimitQuery = Annotated[
    int | None,
    Query(
        ge=1,
        le=MOST_NEAR_LIMIT,
        description=(
            "At most how many close names to offer. Deliberately small: this is a "
            "question to put to a person, not a listing to read."
        ),
    ),
]
NearKeepQuery = Annotated[
    float | None,
    Query(
        ge=0.0,
        le=1.0,
        description=(
            "How close to the best candidate a name has to be to be offered "
            "alongside it, as a share of the best score. `1.0` offers only names "
            "that matched exactly as well; lower values widen the field."
        ),
    ),
]


@dataclass(frozen=True)
class NearLimits:
    """How forgiving one near-name answer may be."""

    limit: int
    keep: float
    floor: float


def near_limits_of(
    request: Request, limit: NearLimitQuery = None, keep: NearKeepQuery = None
) -> NearLimits:
    """Read `k` and `p` from the caller, falling back to the settings.

    The floor under which nothing is offered is never a caller's choice.
    """
    settings = settings_of(request)
    return NearLimits(
        limit=limit if limit is not None else settings.near_limit,
        keep=keep if keep is not None else settings.near_keep,
        floor=settings.near_floor,
    )


NearLimitsDep = Annotated[NearLimits, Depends(near_limits_of)]

DEFAULT_LIMIT = DEFAULT_PAGE_SIZE


# test cases


def _bounds(alias: object) -> dict[str, object]:
    from typing import get_args

    from annotated_types import Ge, Le

    _, declared = get_args(alias)
    found: dict[str, object] = {}
    for bound in declared.metadata:
        if isinstance(bound, Ge):
            found["ge"] = bound.ge
        if isinstance(bound, Le):
            found["le"] = bound.le
    return found


def test_a_page_can_never_be_asked_to_be_unbounded() -> None:
    assert _bounds(LimitQuery) == {"ge": 1, "le": MAX_PAGE_SIZE}


def test_a_page_can_never_start_before_the_beginning() -> None:
    assert _bounds(OffsetQuery) == {"ge": 0}


def test_several_types_can_be_asked_for_under_one_word() -> None:
    from typing import get_args

    _, declared = get_args(TypesQuery)
    assert declared.alias == "type"


def test_every_bounded_parameter_explains_itself_to_a_reader() -> None:
    from typing import get_args

    declared = [
        get_args(alias)[1]
        for alias in (LimitQuery, OffsetQuery, TypesQuery, OrderQuery, DirectionQuery)
    ]
    assert all(parameter.description for parameter in declared)


def test_the_default_page_is_the_one_the_model_declares() -> None:
    assert DEFAULT_LIMIT == DEFAULT_PAGE_SIZE


def test_a_near_name_answer_can_never_be_asked_to_be_a_listing() -> None:
    assert _bounds(NearLimitQuery) == {"ge": 1, "le": MOST_NEAR_LIMIT}


def test_how_close_is_close_enough_is_a_share_of_the_best_match() -> None:
    assert _bounds(NearKeepQuery) == {"ge": 0.0, "le": 1.0}


def _asked(**given: object) -> NearLimits:
    from starlette.requests import Request as Incoming

    request = Incoming(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/near-names",
            "headers": [],
            "query_string": b"",
            "app": _application(),
        }
    )
    return near_limits_of(request, **given)  # type: ignore[arg-type]


def _application() -> object:
    class Held:
        state = type("State", (), {SETTINGS_STATE: Settings()})()

    return Held()


def test_a_caller_who_says_nothing_gets_what_the_deployment_chose() -> None:
    settings = Settings()
    assert _asked() == NearLimits(
        limit=settings.near_limit, keep=settings.near_keep, floor=settings.near_floor
    )


def test_a_caller_can_ask_for_fewer_and_closer_names() -> None:
    asked = _asked(limit=2, keep=1.0)
    assert asked.limit == 2
    assert asked.keep == 1.0


def test_how_poor_the_best_match_may_be_is_never_a_caller_choice() -> None:
    import inspect

    assert "floor" not in inspect.signature(near_limits_of).parameters
