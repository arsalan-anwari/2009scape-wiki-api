"""Stamp and validate responses, which never change while one build is being served.

A caller pinned to a build with `?v=` may hold the answer forever.
"""

from __future__ import annotations

from hashlib import blake2s
from http import HTTPStatus
from typing import TYPE_CHECKING, Final
from wsgiref.handlers import format_date_time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from wiki_api.surfaces.http.dependencies import provider_of
from wiki_api.surfaces.http.errors import error_response
from wiki_api.surfaces.http.schemas import ErrorCode

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.types import ASGIApp

    from wiki_api.config import Settings
    from wiki_api.domain.manifest import Manifest

PIN_PARAMETER: Final = "v"
DATA_VERSION_HEADER: Final = "x-data-version"
PINNED_CACHE_CONTROL: Final = "public, max-age=31536000, immutable"
NO_STORE: Final = "no-store"
READ_METHODS: Final = frozenset({"GET", "HEAD"})
PIN_MESSAGE: Final = (
    "this build is no longer being served; retry against the current one"
)


def validator(data_version: str, path: str, query: Iterable[tuple[str, str]]) -> str:
    """Build the weak ETag standing in for one exact response."""
    asked = "&".join(f"{name}={value}" for name, value in sorted(query))
    digest = blake2s(
        f"{data_version}\n{path}\n{asked}".encode(), digest_size=8
    ).hexdigest()
    return f'W/"{data_version}:{digest}"'


class Validators(BaseHTTPMiddleware):
    """Stamp every answer with what it was built from, and answer 304 on a re-ask."""

    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in READ_METHODS:
            return await call_next(request)
        manifest = provider_of(request).current().manifest()
        pinned = request.query_params.get(PIN_PARAMETER)
        if pinned is not None and pinned != manifest.data_version:
            return error_response(
                HTTPStatus.CONFLICT,
                ErrorCode.DATA_VERSION_MISMATCH,
                PIN_MESSAGE,
                data_version=manifest.data_version,
                headers={DATA_VERSION_HEADER: manifest.data_version},
            )
        tag = validator(
            manifest.data_version, request.url.path, request.query_params.items()
        )
        headers = self._headers(manifest, tag, pinned is not None)
        if request.headers.get("if-none-match") == tag:
            return Response(status_code=int(HTTPStatus.NOT_MODIFIED), headers=headers)
        response = await call_next(request)
        if response.status_code == int(HTTPStatus.OK):
            self._stamp(response, headers)
        return response

    def _headers(self, manifest: Manifest, tag: str, pinned: bool) -> dict[str, str]:
        return {
            DATA_VERSION_HEADER: manifest.data_version,
            "etag": tag,
            "last-modified": http_date(manifest.built_at.timestamp()),
            "cache-control": PINNED_CACHE_CONTROL
            if pinned
            else f"public, max-age={self._settings.cache_seconds}",
        }

    def _stamp(self, response: Response, headers: dict[str, str]) -> None:
        chosen = "cache-control" not in response.headers
        for name, value in headers.items():
            if name == "cache-control" and not chosen:
                continue
            response.headers[name] = value


def stamp_freshness(response: Response, seconds: int) -> None:
    """Say how long this particular answer may be held before it is asked for again."""
    response.headers["cache-control"] = f"public, max-age={seconds}"


def decline_caching(response: Response) -> None:
    """Say that this answer is about the process, not about the game."""
    response.headers["cache-control"] = NO_STORE


def http_date(moment: float) -> str:
    """Write a moment the way a validator header wants it."""
    return format_date_time(moment)


# test cases


def test_the_same_question_of_the_same_build_validates_the_same() -> None:
    first = validator("fixture-0001", "/v1/entities/item/4587", [])
    again = validator("fixture-0001", "/v1/entities/item/4587", [])
    assert first == again


def test_a_new_build_invalidates_everything_that_came_before() -> None:
    before = validator("fixture-0001", "/v1/entities/item/4587", [])
    after = validator("fixture-0002", "/v1/entities/item/4587", [])
    assert before != after


def test_two_different_questions_do_not_share_a_validator() -> None:
    page = validator("fixture-0001", "/v1/entities/item/4587", [])
    hover = validator("fixture-0001", "/v1/entities/item/4587/tooltip", [])
    assert page != hover


def test_asking_the_same_thing_with_the_words_reordered_validates_the_same() -> None:
    one_way = validator("f", "/v1/search", [("q", "dragon"), ("limit", "10")])
    other = validator("f", "/v1/search", [("limit", "10"), ("q", "dragon")])
    assert one_way == other


def test_a_validator_is_weak_because_a_body_may_be_compressed() -> None:
    assert validator("fixture-0001", "/v1/about", []).startswith('W/"')


def test_a_validator_says_which_build_it_came_from() -> None:
    assert "fixture-0001" in validator("fixture-0001", "/v1/about", [])


def test_an_answer_about_the_process_is_never_held() -> None:
    response = Response()
    decline_caching(response)
    assert response.headers["cache-control"] == NO_STORE


def test_an_answer_about_the_game_says_how_long_it_keeps() -> None:
    response = Response()
    stamp_freshness(response, 3600)
    assert response.headers["cache-control"] == "public, max-age=3600"


def test_a_moment_is_written_the_way_the_transport_expects() -> None:
    assert http_date(0.0) == "Thu, 01 Jan 1970 00:00:00 GMT"
