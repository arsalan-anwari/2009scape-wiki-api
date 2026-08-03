"""Turn a directory of documents into a snapshot and write it out."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.pipeline.artifact.merge import merge
from wiki_api.pipeline.artifact.overlay import load_documents
from wiki_api.pipeline.artifact.writer import write_artifact

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.provenance import GameVersion
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot


def build_snapshot(source_dir: Path, *, strict: bool = True) -> KnowledgeSnapshot:
    """Read every document in a directory and merge them, with no staged sources."""
    return merge(load_documents(source_dir), strict=strict)


def build_artifact(
    source_dir: Path,
    destination: Path,
    *,
    data_version: str,
    game_version: GameVersion | str,
    built_at: datetime,
    strict: bool = True,
) -> Manifest:
    """Build a snapshot from documents alone and write it out in one step."""
    snapshot = build_snapshot(source_dir, strict=strict)
    return write_artifact(
        snapshot,
        destination,
        data_version=data_version,
        game_version=game_version,
        built_at=built_at,
    )


# test cases


def test_a_document_build_writes_an_artifact(tmp_path: Path) -> None:
    import json
    from datetime import UTC, datetime

    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "items.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "fixture",
                "game_version": "test",
                "entities": [{"type": "item", "id": 995, "name": "Coins"}],
            }
        ),
        encoding="utf-8",
    )
    manifest = build_artifact(
        documents,
        tmp_path / "knowledge.sqlite3",
        data_version="test-0001",
        game_version="test",
        built_at=datetime(2026, 8, 3, tzinfo=UTC),
    )
    assert manifest.data_version == "test-0001"
    assert (tmp_path / "knowledge.sqlite3").is_file()
