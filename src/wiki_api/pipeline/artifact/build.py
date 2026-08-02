"""Run a whole build, from the documents on disk to the finished artifact."""

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
    """Read every document under the given directory and merge them."""
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
    """Build a snapshot and write it out in one step."""
    snapshot = build_snapshot(source_dir, strict=strict)
    return write_artifact(
        snapshot,
        destination,
        data_version=data_version,
        game_version=game_version,
        built_at=built_at,
    )
