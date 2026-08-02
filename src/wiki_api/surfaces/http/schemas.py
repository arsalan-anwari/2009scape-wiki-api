"""Hold the shapes this surface adds to the core's: a failure, a health check and an
inspected resolution.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.core import Hidden, Missing, Moved
from wiki_api.domain.identity import Link


class ErrorCode(StrEnum):
    """Why a request did not produce what it asked for, in a word to branch on."""

    NOT_FOUND = "not_found"
    NOT_PUBLISHED = "not_published"
    INVALID_REQUEST = "invalid_request"
    DATA_VERSION_MISMATCH = "data_version_mismatch"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    UNAUTHENTICATED = "unauthenticated"
    BLOCKED = "blocked"
    THROTTLED = "throttled"
    UNEXPECTED = "unexpected"


class ErrorDetail(BaseModel):
    """What went wrong: a `code` to branch on and a `message` to read.

    `data_version` is the build still served when the one asked for is gone;
    `near_names_url` is where to ask what an unmatched name might have meant.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    data_version: str | None = None
    near_names: str | None = None


class ErrorBody(BaseModel):
    """The envelope every error arrives in: one `error` object, nothing else."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail

    @classmethod
    def of(
        cls,
        code: ErrorCode,
        message: str,
        data_version: str | None = None,
        near_names: str | None = None,
    ) -> ErrorBody:
        return cls(
            error=ErrorDetail(
                code=code.value,
                message=message,
                data_version=data_version,
                near_names=near_names,
            )
        )


class Health(BaseModel):
    """The server is answering, and the build it answers from."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    data_version: str
    schema_version: int


class Present(BaseModel):
    """The reference points at an entity that is published right now."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["found"] = "found"
    target: Link


Resolution = Annotated[
    Present | Moved | Hidden | Missing, Field(discriminator="outcome")
]


# test cases


def test_a_failure_reads_the_same_way_whatever_caused_it() -> None:
    body = ErrorBody.of(ErrorCode.NOT_FOUND, "no such entity")
    assert body.model_dump(mode="json", exclude_none=True) == {
        "error": {"code": "not_found", "message": "no such entity"}
    }


def test_a_name_that_meant_nothing_says_where_to_ask_what_it_might_have_meant() -> None:
    body = ErrorBody.of(
        ErrorCode.NOT_FOUND, "no such entity", None, "/v1/near-names?name=x&type=item"
    )
    assert body.error.near_names == "/v1/near-names?name=x&type=item"


def test_a_failure_that_has_nothing_to_suggest_suggests_nothing() -> None:
    body = ErrorBody.of(ErrorCode.NOT_FOUND, "no such entity")
    assert body.model_dump(exclude_none=True) == {
        "error": {"code": "not_found", "message": "no such entity"}
    }


def test_a_failure_a_caller_can_recover_from_says_what_to_retry_against() -> None:
    body = ErrorBody.of(ErrorCode.DATA_VERSION_MISMATCH, "gone", "2026.08.02")
    assert body.error.data_version == "2026.08.02"


def test_a_hidden_entity_is_told_apart_from_one_that_is_not_there() -> None:
    assert len({ErrorCode.NOT_PUBLISHED, ErrorCode.NOT_FOUND}) == 2


def test_health_says_which_build_answers() -> None:
    health = Health(data_version="fixture-0001", schema_version=4)
    assert health.status == "ok"
    assert health.data_version == "fixture-0001"


def test_every_resolution_names_its_own_outcome() -> None:
    from pydantic import TypeAdapter

    from wiki_api.domain.identity import EntityType

    link = Link(type=EntityType.ITEM, id=4587, slug="dragon-scimitar", label="Dragon")
    adapter: TypeAdapter[Resolution] = TypeAdapter(Resolution)
    answers = (Present(target=link), Moved(target=link), Missing(reference="item:1"))
    for value in answers:
        restored = adapter.validate_json(adapter.dump_json(value))
        assert restored == value
