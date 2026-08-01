"""Holding the artifact a surface is currently reading, so it can be replaced while the
process keeps serving. Replacing it hands the old one back rather than closing it, since
requests in flight are still reading from it.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Self

from wiki_api.repository.factory import open_repository

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.repository.protocol import KnowledgeRepository


class RepositoryProvider:
    """One indirection between a surface and the artifact it reads."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository
        self._lock = threading.Lock()

    @classmethod
    def open(cls, path: Path) -> Self:
        """Open the artifact at a path and hold it."""
        return cls(open_repository(path))

    def current(self) -> KnowledgeRepository:
        """Whatever is being served right now."""
        with self._lock:
            return self._repository

    def swap(self, repository: KnowledgeRepository) -> KnowledgeRepository:
        """Serve something else from here on, and hand back what was being served."""
        with self._lock:
            replaced, self._repository = self._repository, repository
        return replaced

    def close(self) -> None:
        """Let go of the artifact."""
        with self._lock:
            self._repository.close()


# test cases


def _repository(name: str) -> KnowledgeRepository:
    from datetime import UTC, datetime

    from wiki_api.domain.manifest import SCHEMA_VERSION, Manifest
    from wiki_api.repository.memory import InMemoryKnowledgeRepository

    manifest = Manifest.model_validate(
        {
            "data_version": name,
            "schema_version": SCHEMA_VERSION,
            "content_hash": "0" * 64,
            "built_at": datetime(2026, 7, 30, tzinfo=UTC),
            "game_version": "2009scape@0000000",
        }
    )
    return InMemoryKnowledgeRepository(manifest)


def test_a_provider_hands_out_what_it_was_opened_with() -> None:
    repository = _repository("first")
    provider = RepositoryProvider(repository)
    assert provider.current() is repository


def test_swapping_hands_back_the_one_that_was_being_served() -> None:
    first = _repository("first")
    second = _repository("second")
    provider = RepositoryProvider(first)
    replaced = provider.swap(second)
    assert replaced is first
    assert provider.current() is second


def test_the_one_that_was_replaced_is_left_open_for_its_readers() -> None:
    first = _repository("first")
    provider = RepositoryProvider(first)
    provider.swap(_repository("second"))
    assert first.manifest().data_version == "first"


def test_closing_a_provider_closes_what_it_holds() -> None:
    repository = _repository("first")
    RepositoryProvider(repository).close()
    assert repository.manifest().data_version == "first"


def test_a_provider_refuses_a_path_with_no_artifact_at_it(tmp_path: Path) -> None:
    import pytest

    from wiki_api.repository.errors import ArtifactUnavailable

    with pytest.raises(ArtifactUnavailable):
        RepositoryProvider.open(tmp_path / "absent.sqlite3")
