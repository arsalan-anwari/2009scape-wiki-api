from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.pipeline.artifact.merge import merge
from wiki_api.pipeline.artifact.overlay import load_documents
from wiki_api.pipeline.artifact.writer import write_artifact

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot


def build_snapshot(source_dir: Path, *, strict: bool = True) -> KnowledgeSnapshot:
    return merge(load_documents(source_dir), strict=strict)


def build_artifact(
    source_dir: Path,
    destination: Path,
    *,
    data_version: str,
    game_version: str,
    built_at: datetime,
    game_commit: str | None = None,
    strict: bool = True,
) -> Manifest:
    snapshot = build_snapshot(source_dir, strict=strict)
    return write_artifact(
        snapshot,
        destination,
        data_version=data_version,
        game_version=game_version,
        built_at=built_at,
        game_commit=game_commit,
    )
