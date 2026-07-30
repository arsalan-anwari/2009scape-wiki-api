"""Settings for the service, read from the environment."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from wiki_api.domain.page import MAX_PAGE_SIZE

if TYPE_CHECKING:
    import pytest


class Settings(BaseSettings):
    """Runtime configuration.

    Every field can be overridden with a WIKI_API_ prefixed environment variable.
    """

    model_config = SettingsConfigDict(
        env_prefix="WIKI_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hf_repo_id: str = "arsalan-anwari/2009scape-wiki-api-data"
    hf_revision: str = "main"
    data_dir: Path = Path("data")
    artifact_filename: str = "knowledge.sqlite3"
    game_data_dir: Path = Path("game_data")
    ge_data_url: str = "https://cdn.2009scape.org/gedata/"
    cors_origins: tuple[str, ...] = ("*",)
    cache_seconds: int = 300
    tooltip_cache_seconds: int = 3600
    block_rows: int = Field(default=60, ge=1, le=MAX_PAGE_SIZE)

    @property
    def artifact_path(self) -> Path:
        return self.data_dir / self.artifact_filename

    @property
    def ge_snapshot_dir(self) -> Path:
        return self.game_data_dir / "grand-exchange-data"


def get_settings() -> Settings:
    """Read the settings fresh from the environment."""
    return Settings()


# test cases


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("WIKI_API_HF_REPO_ID", "WIKI_API_HF_REVISION", "WIKI_API_DATA_DIR"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.hf_repo_id == "arsalan-anwari/2009scape-wiki-api-data"
    assert settings.hf_revision == "main"
    assert settings.data_dir == Path("data")


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKI_API_HF_REVISION", "abc123")
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    settings = Settings()
    assert settings.hf_revision == "abc123"
    assert settings.data_dir == Path("/srv/wiki")


def test_the_artifact_path_lives_under_the_data_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_ARTIFACT_FILENAME", raising=False)
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    assert Settings().artifact_path == Path("/srv/wiki/knowledge.sqlite3")


def test_the_artifact_filename_is_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_DATA_DIR", "/srv/wiki")
    monkeypatch.setenv("WIKI_API_ARTIFACT_FILENAME", "knowledge-2026.sqlite3")
    assert Settings().artifact_path == Path("/srv/wiki/knowledge-2026.sqlite3")


def test_raw_game_sources_live_outside_the_artifact_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_GAME_DATA_DIR", "/srv/raw")
    settings = Settings()
    assert settings.ge_snapshot_dir == Path("/srv/raw/grand-exchange-data")
    assert settings.data_dir not in settings.ge_snapshot_dir.parents


def test_the_grand_exchange_host_is_not_hardcoded_in_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_GE_DATA_URL", "https://example.test/prices/")
    assert Settings().ge_data_url == "https://example.test/prices/"


def test_a_browser_front_end_is_allowed_in_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_CORS_ORIGINS", raising=False)
    assert Settings().cors_origins == ("*",)


def test_the_origins_allowed_in_are_configurable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_CORS_ORIGINS", '["https://wiki.example.test"]')
    assert Settings().cors_origins == ("https://wiki.example.test",)


def test_a_hover_is_held_longer_than_a_page(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("WIKI_API_CACHE_SECONDS", "WIKI_API_TOOLTIP_CACHE_SECONDS"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    assert settings.tooltip_cache_seconds > settings.cache_seconds


def test_a_page_shows_enough_rows_to_be_worth_reading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WIKI_API_BLOCK_ROWS", raising=False)
    assert Settings().block_rows == 60


def test_how_many_rows_a_page_shows_is_tunable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WIKI_API_BLOCK_ROWS", "25")
    assert Settings().block_rows == 25


def test_a_page_can_never_be_configured_to_be_unbounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytest as testing

    monkeypatch.setenv("WIKI_API_BLOCK_ROWS", str(MAX_PAGE_SIZE + 1))
    with testing.raises(ValueError):
        Settings()
