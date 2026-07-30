"""Turning everything that can go wrong into one shape a client can branch on.

A route raises; the handlers here decide the status and write the envelope. Nothing
below this module knows what a status code is, and nothing a client receives carries a
stack trace, a file path, or an internal identifier.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from wiki_api.domain.errors import KnowledgeError
from wiki_api.surfaces.http.schemas import ErrorBody, ErrorCode

if TYPE_CHECKING:
    from starlette.requests import Request

REDIRECT_STATUS = HTTPStatus.PERMANENT_REDIRECT
UNAVAILABLE_MESSAGE = "the knowledge base is not available"
UNEXPECTED_MESSAGE = "the request could not be completed"


class ContractError(Exception):
    """A request that cannot be answered, phrased the way a client reads it."""

    def __init__(self, status: HTTPStatus, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class Redirect(Exception):
    """The thing asked for now answers somewhere else in this api."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


def error_response(
    status: HTTPStatus,
    code: ErrorCode,
    message: str,
    *,
    data_version: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """One failure, written into the envelope every other failure uses."""
    body = ErrorBody.of(code, message, data_version)
    return JSONResponse(
        status_code=int(status),
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


def install(app: FastAPI) -> None:
    """Teach an application every way this surface reports a failure."""
    app.add_exception_handler(Redirect, _redirect)
    app.add_exception_handler(ContractError, _contract)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(StarletteHTTPException, _transport)
    app.add_exception_handler(KnowledgeError, _unavailable)
    app.add_exception_handler(Exception, _unexpected)


async def _redirect(request: Request, error: Exception) -> Response:
    assert isinstance(error, Redirect)
    query = request.url.query
    location = f"{error.path}?{query}" if query else error.path
    return Response(status_code=int(REDIRECT_STATUS), headers={"location": location})


async def _contract(request: Request, error: Exception) -> Response:
    assert isinstance(error, ContractError)
    return error_response(error.status, error.code, error.message)


async def _invalid(request: Request, error: Exception) -> Response:
    assert isinstance(error, RequestValidationError)
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY, ErrorCode.INVALID_REQUEST, _summarise(error)
    )


async def _transport(request: Request, error: Exception) -> Response:
    assert isinstance(error, StarletteHTTPException)
    status = HTTPStatus(error.status_code)
    code = (
        ErrorCode.NOT_FOUND
        if status is HTTPStatus.NOT_FOUND
        else ErrorCode.INVALID_REQUEST
    )
    return error_response(status, code, str(error.detail))


async def _unavailable(request: Request, error: Exception) -> Response:
    return error_response(
        HTTPStatus.SERVICE_UNAVAILABLE,
        ErrorCode.ARTIFACT_UNAVAILABLE,
        UNAVAILABLE_MESSAGE,
    )


async def _unexpected(request: Request, error: Exception) -> Response:
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, ErrorCode.UNEXPECTED, UNEXPECTED_MESSAGE
    )


def _summarise(error: RequestValidationError) -> str:
    reported = error.errors()
    if not reported:
        return "the request could not be read"
    first = reported[0]
    where = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = str(first.get("msg", "is not acceptable"))
    return f"{where}: {message}" if where else message


# test cases


def test_a_failure_body_carries_a_code_a_client_can_branch_on() -> None:
    import json

    response = error_response(
        HTTPStatus.NOT_FOUND, ErrorCode.NOT_FOUND, "no such entity"
    )
    assert response.status_code == 404
    assert json.loads(bytes(response.body)) == {
        "error": {"code": "not_found", "message": "no such entity"}
    }


def test_a_contract_failure_keeps_the_words_it_was_raised_with() -> None:
    error = ContractError(
        HTTPStatus.NOT_FOUND, ErrorCode.NOT_PUBLISHED, "not published"
    )
    assert error.status is HTTPStatus.NOT_FOUND
    assert error.code is ErrorCode.NOT_PUBLISHED
    assert str(error) == "not published"


def test_a_redirect_remembers_where_it_is_sending_the_caller() -> None:
    assert Redirect("/v1/entities/item/4587").path == "/v1/entities/item/4587"


def test_an_unreadable_request_is_summarised_rather_than_dumped() -> None:
    error = RequestValidationError(
        [{"loc": ("query", "limit"), "msg": "is too large", "type": "value_error"}]
    )
    assert _summarise(error) == "query.limit: is too large"


def test_a_request_that_says_nothing_about_itself_still_summarises() -> None:
    assert _summarise(RequestValidationError([])) == "the request could not be read"


def _request() -> Request:
    from starlette.requests import Request as Incoming

    return Incoming(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/about",
            "headers": [],
            "query_string": b"",
        }
    )


def test_a_knowledge_base_that_cannot_answer_is_reported_as_unavailable() -> None:
    import asyncio
    import json

    from wiki_api.domain.errors import CorruptArtifact

    failure = CorruptArtifact("entity", "type", "banana")
    response = asyncio.run(_unavailable(_request(), failure))
    assert response.status_code == 503
    reported = json.loads(bytes(response.body))
    assert reported["error"]["code"] == "artifact_unavailable"
    assert "banana" not in reported["error"]["message"]


def test_something_nobody_foresaw_still_arrives_in_the_envelope() -> None:
    import asyncio
    import json

    response = asyncio.run(_unexpected(_request(), RuntimeError("a division by zero")))
    assert response.status_code == 500
    reported = json.loads(bytes(response.body))
    assert reported["error"]["code"] == "unexpected"
    assert "division" not in reported["error"]["message"]


def test_a_route_nobody_serves_is_reported_as_plainly_absent() -> None:
    import asyncio
    import json

    failure = StarletteHTTPException(status_code=404, detail="Not Found")
    response = asyncio.run(_transport(_request(), failure))
    assert json.loads(bytes(response.body))["error"]["code"] == "not_found"


def test_a_method_nobody_serves_is_reported_as_an_unusable_request() -> None:
    import asyncio
    import json

    failure = StarletteHTTPException(status_code=405, detail="Method Not Allowed")
    response = asyncio.run(_transport(_request(), failure))
    assert json.loads(bytes(response.body))["error"]["code"] == "invalid_request"


def test_every_way_this_surface_fails_is_installed_on_the_application() -> None:
    app = FastAPI()
    install(app)
    installed = set(app.exception_handlers)
    expected = {Redirect, ContractError, RequestValidationError, KnowledgeError}
    assert expected <= installed
