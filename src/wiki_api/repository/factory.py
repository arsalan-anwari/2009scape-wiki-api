"""The one place a concrete repository is chosen and opened; everything above it speaks
to the protocol instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.repository.sqlite import SqliteKnowledgeRepository

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.repository.protocol import KnowledgeRepository


def open_repository(path: Path) -> KnowledgeRepository:
    """Open a built artifact for reading, refusing one whose schema version this runtime
    cannot read.
    """
    return SqliteKnowledgeRepository(path)


# test cases


def test_a_missing_artifact_is_reported_before_it_is_read(tmp_path: Path) -> None:
    import pytest

    from wiki_api.repository.errors import ArtifactUnavailable

    with pytest.raises(ArtifactUnavailable):
        open_repository(tmp_path / "absent.sqlite3")


def test_a_file_that_is_not_an_artifact_is_reported_as_unreadable(
    tmp_path: Path,
) -> None:
    import pytest

    from wiki_api.repository.errors import ArtifactUnreadable

    path = tmp_path / "knowledge.sqlite3"
    path.write_text("this is not a database")
    with pytest.raises(ArtifactUnreadable):
        open_repository(path)
