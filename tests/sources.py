"""Build a staged directory in a temporary place, for tests that read one."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from wiki_api.domain.provenance import GameVersion
from wiki_api.pipeline.sources.staged import StagedSources
from wiki_api.pipeline.staging.collectors import CACHE, CONFIGS, PRICES, TABLES
from wiki_api.pipeline.staging.manifest import (
    StagedFile,
    StagingManifest,
    digest_of,
    write_manifest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

STAGED_VERSION = "2009scape@1f4a2c9"
STAGED_AT = datetime(2026, 8, 3, tzinfo=UTC)


def staged_from(
    root: Path,
    files: Mapping[str, str | bytes],
    prices: Sequence[str] = (),
    game_version: str = STAGED_VERSION,
    revisions: Mapping[str, str] | None = None,
) -> StagedSources:
    """Write these files under a staged directory and describe them in a manifest."""
    priced = set(prices)
    recorded = revisions or {}
    entries: list[StagedFile] = []
    for name, payload in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, bytes):
            target.write_bytes(payload)
        else:
            target.write_text(payload, encoding="utf-8")
        entries.append(
            StagedFile(
                path=name,
                digest=digest_of(target),
                size=target.stat().st_size,
                collector=_collector(name, priced),
                collector_version=1,
                game_version=GameVersion.model_validate(game_version),
                upstream=None,
                source_revision=recorded.get(name),
            )
        )
    write_manifest(root, StagingManifest(staged_at=STAGED_AT, files=tuple(entries)))
    return StagedSources.at(root)


def _collector(name: str, priced: set[str]) -> str:
    if name in priced:
        return PRICES
    if name.startswith(f"{CACHE}/"):
        return CACHE
    return TABLES if name.startswith(f"{TABLES}/") else CONFIGS


# test cases


def test_a_written_file_reads_back_through_the_manifest(tmp_path: Path) -> None:
    staged = staged_from(tmp_path, {"configs/item_configs.json": "[]"})
    assert staged.path("configs/item_configs.json").read_text() == "[]"
    assert staged.drifted() == ()


def test_a_price_snapshot_is_listed_as_one(tmp_path: Path) -> None:
    staged = staged_from(
        tmp_path,
        {"grand-exchange/2024-06-08.json": "[]"},
        prices=("grand-exchange/2024-06-08.json",),
    )
    assert [path.name for path in staged.price_files()] == ["2024-06-08.json"]


def test_a_table_is_told_apart_from_a_config(tmp_path: Path) -> None:
    staged = staged_from(tmp_path, {"tables/Quests.json": "{}"})
    assert staged.manifest.by_collector(TABLES)
    assert not staged.manifest.by_collector(CONFIGS)
