"""What a route is handed and what it may be asked for: the repository reached through
the provider on every request, and the query parameters every listing shares.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Query
from starlette.requests import Request

from wiki_api.config import Settings
from wiki_api.core import Direction, KnowledgeService
from wiki_api.domain.identity import EntityType
from wiki_api.domain.manifest import Manifest
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, SortOrder
from wiki_api.repository.provider import RepositoryProvider

PROVIDER_STATE = "provider"
SETTINGS_STATE = "settings"


def provider_of(request: Request) -> RepositoryProvider:
    """The holder this application was started with."""
    return cast(RepositoryProvider, getattr(request.app.state, PROVIDER_STATE))


def settings_of(request: Request) -> Settings:
    """The configuration this application was started with."""
    return cast(Settings, getattr(request.app.state, SETTINGS_STATE))


def service_of(request: Request) -> KnowledgeService:
    """A way to ask questions of whatever is being served right now, widened to the page
    size this deployment's settings ask for.
    """
    return KnowledgeService(
        provider_of(request).current(), block_size=settings_of(request).block_rows
    )


def manifest_of(request: Request) -> Manifest:
    """What the artifact being served says about itself."""
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
    """How many rows one page of a relationship holds, answering at the width the entity
    page used when the caller does not say.
    """
    return limit if limit is not None else settings_of(request).block_rows


RowsDep = Annotated[int, Depends(rows_of)]

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
