"""What a built artifact records about itself."""

from __future__ import annotations

from typing import Final

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from wiki_api.domain.provenance import GameVersion

SCHEMA_VERSION: Final = 4


class Manifest(BaseModel):
    """What a build says about itself: its data-version, the state of the game behind
    it, and a hash fixing its contents.
    """

    model_config = ConfigDict(frozen=True)

    data_version: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    content_hash: str = Field(min_length=1)
    built_at: AwareDatetime
    game_version: GameVersion

    @property
    def is_readable(self) -> bool:
        return self.schema_version == SCHEMA_VERSION

    @property
    def game_commit(self) -> str | None:
        return self.game_version.commit


# test cases


def _manifest(**overrides: object) -> Manifest:
    payload: dict[str, object] = {
        "data_version": "2026.07.25",
        "schema_version": SCHEMA_VERSION,
        "content_hash": "0" * 64,
        "built_at": "2026-07-25T00:00:00+00:00",
        "game_version": "2009scape@1f4a2c9",
    }
    payload.update(overrides)
    return Manifest.model_validate(payload)


def test_an_artifact_of_the_current_schema_version_is_readable() -> None:
    assert _manifest().is_readable is True


def test_an_artifact_from_another_schema_version_is_not_readable() -> None:
    assert _manifest(schema_version=SCHEMA_VERSION + 1).is_readable is False


def test_a_manifest_needs_a_data_version_and_a_content_hash() -> None:
    import pytest

    for overrides in ({"data_version": ""}, {"content_hash": ""}):
        with pytest.raises(ValueError):
            _manifest(**overrides)


def test_the_commit_is_read_off_the_game_version_rather_than_stored_twice() -> None:
    assert _manifest().game_commit == "1f4a2c9"
    assert _manifest(game_version="test").game_commit is None
    assert "game_commit" not in Manifest.model_fields


def test_a_build_time_without_a_timezone_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        _manifest(built_at="2026-07-25T00:00:00")


def test_the_game_version_survives_a_round_trip() -> None:
    manifest = _manifest()
    assert str(manifest.game_version) == "2009scape@1f4a2c9"
    assert manifest.model_dump()["game_version"] == "2009scape@1f4a2c9"
