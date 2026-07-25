from __future__ import annotations

import pytest

from wiki_api.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings()
