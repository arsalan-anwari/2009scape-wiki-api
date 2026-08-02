"""Errors storage raises when the artifact is missing or unreadable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.errors import KnowledgeError

if TYPE_CHECKING:
    from pathlib import Path


class ArtifactUnavailable(KnowledgeError):
    """There is no artifact at the path we were pointed at."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"no knowledge artifact at {path}")
        self.path = path


class ArtifactUnreadable(KnowledgeError):
    """The artifact is there but could not be opened."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"the artifact at {path} could not be read: {detail}")
        self.path = path
        self.detail = detail


# test cases


def test_a_missing_artifact_names_the_path_it_looked_for() -> None:
    from pathlib import Path

    error = ArtifactUnavailable(Path("/data/knowledge.sqlite3"))
    assert "/data/knowledge.sqlite3" in str(error)
    assert isinstance(error, KnowledgeError)


def test_an_unreadable_artifact_carries_the_underlying_detail() -> None:
    from pathlib import Path

    error = ArtifactUnreadable(Path("/data/knowledge.sqlite3"), "no such table: entity")
    assert "no such table: entity" in str(error)
