from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    import pytest


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WIKI_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hf_repo_id: str = "arsalan-anwari/2009scape-wiki-api-data"
    hf_revision: str = "main"
    data_dir: Path = Path("data")


def get_settings() -> Settings:
    return Settings()


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
