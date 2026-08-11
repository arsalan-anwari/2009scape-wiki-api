"""Turn one decision about a caller into one HTTP answer.

A middleware rather than a per-route dependency, so it also covers any application
mounted underneath this one.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Final

from starlette.middleware.base import BaseHTTPMiddleware

from wiki_api.surfaces.guarding import (
    FORWARDED_HEADER,
    Access,
    Outcome,
    anonymous,
    caller_of,
    token_of,
)
from wiki_api.surfaces.http.errors import error_response
from wiki_api.surfaces.http.schemas import ErrorCode

if TYPE_CHECKING:
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

PRIVATE_CACHE_CONTROL: Final = "private"
CHALLENGE: Final = "Bearer"
UNAUTHENTICATED_MESSAGE: Final = "this service answers holders of an issued key"
BLOCKED_MESSAGE: Final = "too many refused requests from this address"
THROTTLED_MESSAGE: Final = "this key has asked for more than its share"

REFUSALS: Final = {
    Outcome.UNAUTHENTICATED: (
        HTTPStatus.UNAUTHORIZED,
        ErrorCode.UNAUTHENTICATED,
        UNAUTHENTICATED_MESSAGE,
    ),
    Outcome.BLOCKED: (HTTPStatus.FORBIDDEN, ErrorCode.BLOCKED, BLOCKED_MESSAGE),
    Outcome.THROTTLED: (
        HTTPStatus.TOO_MANY_REQUESTS,
        ErrorCode.THROTTLED,
        THROTTLED_MESSAGE,
    ),
}


class Guarded(BaseHTTPMiddleware):
    """Answers holders of an issued key, and keeps a shared cache out of it."""

    def __init__(self, app: ASGIApp, *, access: Access) -> None:
        super().__init__(app)
        self._access = access

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if anonymous(request.url.path):
            return await call_next(request)
        decision = self._access.decide(
            token_of(request.headers.get("authorization")),
            caller_of(
                request.client.host if request.client else None,
                request.headers.get(FORWARDED_HEADER),
                self._access.trusted,
            ),
        )
        if not decision.allowed:
            return _refusal(decision.outcome, decision.after)
        response = await call_next(request)
        _kept_private(response)
        return response


def _refusal(outcome: Outcome, after: int | None) -> Response:
    status, code, message = REFUSALS[outcome]
    headers = {"cache-control": "no-store"}
    if outcome is Outcome.UNAUTHENTICATED:
        headers["www-authenticate"] = CHALLENGE
    if after is not None:
        headers["retry-after"] = str(after)
    return error_response(status, code, message, headers=headers)


def _kept_private(response: Response) -> None:
    """Mark a guarded answer `private`, so no cache in between holds it.

    The body is the same for every caller, so a shared cache would hand it to
    callers that presented no key at all.
    """
    held = response.headers.get("cache-control")
    if held is None:
        response.headers["cache-control"] = PRIVATE_CACHE_CONTROL
        return
    if "private" in held or "no-store" in held:
        return
    response.headers["cache-control"] = held.replace("public", PRIVATE_CACHE_CONTROL, 1)


# test cases


def test_every_way_of_being_refused_has_a_status_and_a_code() -> None:
    for outcome in (Outcome.UNAUTHENTICATED, Outcome.BLOCKED, Outcome.THROTTLED):
        status, code, message = REFUSALS[outcome]
        assert status >= HTTPStatus.BAD_REQUEST
        assert code
        assert message


def test_being_answered_is_not_a_refusal() -> None:
    assert Outcome.ALLOWED not in REFUSALS


def test_a_refusal_never_says_which_refusal_it_was() -> None:
    _, _, unauthenticated = REFUSALS[Outcome.UNAUTHENTICATED]
    for word in ("signature", "withdrawn", "malformed", "revoked", "expired"):
        assert word not in unauthenticated


def test_a_caller_with_no_key_is_told_what_would_answer() -> None:
    response = _refusal(Outcome.UNAUTHENTICATED, None)
    assert response.status_code == int(HTTPStatus.UNAUTHORIZED)
    assert response.headers["www-authenticate"] == CHALLENGE


def test_a_caller_over_its_share_is_told_when_to_come_back() -> None:
    response = _refusal(Outcome.THROTTLED, 12)
    assert response.status_code == int(HTTPStatus.TOO_MANY_REQUESTS)
    assert response.headers["retry-after"] == "12"


def test_a_shut_out_address_is_refused_outright() -> None:
    response = _refusal(Outcome.BLOCKED, 900)
    assert response.status_code == int(HTTPStatus.FORBIDDEN)
    assert response.headers["retry-after"] == "900"


def test_no_refusal_is_ever_held_by_anything() -> None:
    for outcome in (Outcome.UNAUTHENTICATED, Outcome.BLOCKED, Outcome.THROTTLED):
        assert _refusal(outcome, None).headers["cache-control"] == "no-store"


def _response(cached: str | None = None) -> Response:
    from starlette.responses import Response as Answer

    answer = Answer()
    if cached is None:
        del answer.headers["cache-control"]
    else:
        answer.headers["cache-control"] = cached
    return answer


def test_an_answer_to_a_key_holder_is_never_held_by_a_shared_cache() -> None:
    answer = _response("public, max-age=300")
    _kept_private(answer)
    assert answer.headers["cache-control"] == "private, max-age=300"


def test_an_answer_that_says_nothing_about_caching_is_made_private() -> None:
    answer = _response()
    _kept_private(answer)
    assert answer.headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_an_answer_that_is_already_private_is_left_alone() -> None:
    answer = _response("no-store")
    _kept_private(answer)
    assert answer.headers["cache-control"] == "no-store"


def test_a_pinned_answer_stays_immutable_but_stops_being_shared() -> None:
    answer = _response("public, max-age=31536000, immutable")
    _kept_private(answer)
    assert answer.headers["cache-control"] == "private, max-age=31536000, immutable"
