from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Final = 3


class Manifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_version: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    content_hash: str = Field(min_length=1)
    built_at: datetime
    game_version: str = Field(min_length=1)
    game_commit: str | None = None

    @property
    def is_readable(self) -> bool:
        return self.schema_version == SCHEMA_VERSION


def test_an_artifact_of_the_current_schema_version_is_readable() -> None:
    manifest = Manifest(
        data_version="2026.07.25",
        schema_version=SCHEMA_VERSION,
        content_hash="0" * 64,
        built_at=datetime.fromisoformat("2026-07-25T00:00:00+00:00"),
        game_version="2009scape@1f4a2c9",
    )
    assert manifest.is_readable is True


def test_an_artifact_from_another_schema_version_is_not_readable() -> None:
    manifest = Manifest(
        data_version="2027.01.01",
        schema_version=SCHEMA_VERSION + 1,
        content_hash="0" * 64,
        built_at=datetime.fromisoformat("2027-01-01T00:00:00+00:00"),
        game_version="2009scape@ffffff",
    )
    assert manifest.is_readable is False


def test_a_manifest_needs_a_data_version_and_a_content_hash() -> None:
    import pytest

    for overrides in ({"data_version": ""}, {"content_hash": ""}):
        payload = {
            "data_version": "2026.07.25",
            "schema_version": SCHEMA_VERSION,
            "content_hash": "0" * 64,
            "built_at": "2026-07-25T00:00:00+00:00",
            "game_version": "2009scape@1f4a2c9",
        }
        payload.update(overrides)
        with pytest.raises(ValueError):
            Manifest.model_validate(payload)
