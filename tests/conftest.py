from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from tests.artifact import FIXTURE_KNOWLEDGE
from wiki_api.access.paths import banned_path, config_dir, revoked_path
from wiki_api.config import Settings
from wiki_api.core import BLOCK_PAGE_SIZE, KnowledgeService
from wiki_api.pipeline.artifact import build_snapshot
from wiki_api.repository.memory import InMemoryKnowledgeRepository
from wiki_api.repository.sqlite import SqliteKnowledgeRepository
from wiki_api.surfaces.http import create_app

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from wiki_api.access.issuing import Issuer
    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.artifact import KnowledgeSnapshot
    from wiki_api.repository.protocol import KnowledgeRepository

ORIGINS = ("https://wiki.example.test",)
MACHINE_CONFIG = config_dir()
"""Where this machine keeps its own keys, read before the suite points elsewhere."""


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def fixture_snapshot() -> KnowledgeSnapshot:
    return build_snapshot(FIXTURE_KNOWLEDGE)


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


@pytest.fixture
def service(repository: KnowledgeRepository) -> KnowledgeService:
    return KnowledgeService(repository)


@pytest.fixture
def http_settings(fixture_artifact: Path, suite_issuer: Issuer) -> Settings:
    """Build settings shaped like a real deployment: key holders only, named origins.

    The default, so a test saying nothing about access exercises how this is served.
    """
    return Settings(
        data_dir=fixture_artifact.parent,
        artifact_filename=fixture_artifact.name,
        auth_revoked_file=revoked_path(suite_issuer.directory),
        ban_file=banned_path(suite_issuer.directory),
        cors_origins=ORIGINS,
    )


@pytest.fixture
def open_settings(fixture_artifact: Path) -> Settings:
    """A deployment that answers everyone, for the tests that are about that."""
    return Settings(
        data_dir=fixture_artifact.parent,
        artifact_filename=fixture_artifact.name,
        auth_mode="off",
        cors_origins=("*",),
    )


@pytest.fixture
def client(http_settings: Settings, bearer: dict[str, str]) -> Iterator[TestClient]:
    """A caller holding a key this deployment answers."""
    with TestClient(create_app(http_settings), headers=bearer) as connected:
        yield connected


@pytest.fixture
def open_client(open_settings: Settings) -> Iterator[TestClient]:
    """A caller of a deployment that asks nobody for anything."""
    with TestClient(create_app(open_settings)) as connected:
        yield connected


@pytest.fixture
def preview_client(
    http_settings: Settings, bearer: dict[str, str]
) -> Iterator[TestClient]:
    settings = http_settings.model_copy(update={"block_rows": BLOCK_PAGE_SIZE})
    with TestClient(create_app(settings), headers=bearer) as connected:
        yield connected
