from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from wiki_api.config import Settings
from wiki_api.pipeline.artifact import build_snapshot, write_artifact
from wiki_api.repository.memory import InMemoryKnowledgeRepository
from wiki_api.repository.sqlite import SqliteKnowledgeRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.artifact import KnowledgeSnapshot
    from wiki_api.repository.protocol import KnowledgeRepository

FIXTURE_KNOWLEDGE = Path(__file__).parent / "fixtures" / "knowledge"
FIXTURE_DATA_VERSION = "fixture-0001"
FIXTURE_GAME_VERSION = "2009scape@5a37f2f8"
FIXTURE_BUILT_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def fixture_snapshot() -> KnowledgeSnapshot:
    return build_snapshot(FIXTURE_KNOWLEDGE)


@pytest.fixture(scope="session")
def fixture_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("artifact") / "knowledge.sqlite3"
    build_fixture_artifact(destination)
    return destination


@pytest.fixture(scope="session")
def fixture_manifest(fixture_artifact: Path) -> Manifest:
    repository = SqliteKnowledgeRepository(fixture_artifact)
    try:
        return repository.manifest()
    finally:
        repository.close()


@pytest.fixture(params=["sqlite", "memory"])
def repository(
    request: pytest.FixtureRequest,
    fixture_artifact: Path,
    fixture_snapshot: KnowledgeSnapshot,
    fixture_manifest: Manifest,
) -> Iterator[KnowledgeRepository]:
    if request.param == "sqlite":
        built: KnowledgeRepository = SqliteKnowledgeRepository(fixture_artifact)
    else:
        built = InMemoryKnowledgeRepository(
            fixture_manifest,
            entities=fixture_snapshot.entities,
            edges=fixture_snapshot.edges,
            aliases=fixture_snapshot.aliases,
            prices=fixture_snapshot.prices,
        )
    try:
        yield built
    finally:
        built.close()


def build_fixture_artifact(
    destination: Path,
    *,
    data_version: str = FIXTURE_DATA_VERSION,
    built_at: datetime = FIXTURE_BUILT_AT,
) -> Manifest:
    return write_artifact(
        build_snapshot(FIXTURE_KNOWLEDGE),
        destination,
        data_version=data_version,
        game_version=FIXTURE_GAME_VERSION,
        built_at=built_at,
    )
