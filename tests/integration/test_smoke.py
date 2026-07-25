from __future__ import annotations

import pytest

import wiki_api
from wiki_api.config import Settings


def test_package_imports_and_exposes_version() -> None:
    assert isinstance(wiki_api.__version__, str)
    assert wiki_api.__version__


def test_settings_resolve_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WIKI_API_HF_REPO_ID", "someone/else")
    settings = Settings()
    assert settings.hf_repo_id == "someone/else"
