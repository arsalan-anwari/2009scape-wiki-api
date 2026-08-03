"""Copy, extract and fetch the declared sources into one staged directory."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import httpx
from pydantic import BaseModel, ConfigDict

from wiki_api.pipeline.enums import read_enum
from wiki_api.pipeline.staging.declared import (
    DECLARED_CONFIGS,
    DECLARED_TABLES,
    GAME_CHECKOUT,
    GAME_REPO,
)
from wiki_api.pipeline.staging.errors import UnknownCollector, UpstreamMissing
from wiki_api.pipeline.staging.manifest import (
    StagedFile,
    StagingManifest,
    digest_of,
    read_manifest_if_staged,
    write_manifest,
)
from wiki_api.pipeline.staging.prices import TIMEOUT, download_snapshots
from wiki_api.pipeline.staging.upstream import game_version_of

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from wiki_api.domain.provenance import GameVersion

CONFIGS: Final = "configs"
TABLES: Final = "tables"
PRICES: Final = "prices"
PRICES_DIRECTORY: Final = "grand-exchange"
CONFIG_VERSION: Final = 1
TABLE_VERSION: Final = 1
PRICE_VERSION: Final = 1
PARTIAL_SUFFIX: Final = ".staging"
JSON_INDENT: Final = 1


@dataclass(frozen=True)
class StagingRun:
    """Where one staging run reads from and writes to."""

    game_data: Path
    destination: Path
    prices_url: str

    @property
    def checkout(self) -> Path:
        return self.game_data / GAME_CHECKOUT

    def upstream(self, collector: str, relative: str) -> Path:
        path = self.checkout / relative
        if not path.is_file():
            raise UpstreamMissing(collector, str(path))
        return path


class CollectorReport(BaseModel):
    """What one collector staged, and anything a reader should know about it."""

    model_config = ConfigDict(frozen=True)

    collector: str
    files: tuple[StagedFile, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.files)


class StagingReport(BaseModel):
    """What a whole staging run did."""

    model_config = ConfigDict(frozen=True)

    destination: str
    game_version: str
    reports: tuple[CollectorReport, ...] = ()

    @property
    def count(self) -> int:
        return sum(report.count for report in self.reports)

    def lines(self) -> tuple[str, ...]:
        told = [f"staged {self.count} files from {self.game_version}"]
        for report in self.reports:
            told.append(f"  {report.collector}: {report.count} files")
            told.extend(f"    {note}" for note in report.notes)
        return tuple(told)


def stage_configs(run: StagingRun, version: GameVersion) -> CollectorReport:
    """Copy every declared config file across without touching its bytes."""
    staged = [
        _write(
            run.destination / declared.staged,
            run.upstream(CONFIGS, declared.upstream).read_bytes(),
            collector=CONFIGS,
            version=CONFIG_VERSION,
            game_version=version,
            upstream=declared.upstream,
            relative=declared.staged,
        )
        for declared in DECLARED_CONFIGS
    ]
    return CollectorReport(collector=CONFIGS, files=tuple(staged))


def stage_tables(run: StagingRun, version: GameVersion) -> CollectorReport:
    """Read every declared enum out of the game's code as a table of named columns."""
    staged: list[StagedFile] = []
    notes: list[str] = []
    for declared in DECLARED_TABLES:
        source = run.upstream(TABLES, declared.upstream)
        table = read_enum(
            source.read_text(encoding="utf-8"), declared.enum, declared.filename
        )
        staged.append(
            _write(
                run.destination / declared.staged,
                _as_json(table.model_dump(mode="json")),
                collector=TABLES,
                version=TABLE_VERSION,
                game_version=version,
                upstream=declared.upstream,
                relative=declared.staged,
            )
        )
        notes.append(
            f"{declared.enum}: {len(table.constants)} rows, "
            f"{len(table.columns)} columns"
        )
    return CollectorReport(collector=TABLES, files=tuple(staged), notes=tuple(notes))


def stage_prices(run: StagingRun, version: GameVersion) -> CollectorReport:
    """Fetch the weekly price snapshots that are not staged yet."""
    destination = run.destination / PRICES_DIRECTORY
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        harvest = download_snapshots(client, run.prices_url, destination)
    staged = [
        StagedFile(
            path=f"{PRICES_DIRECTORY}/{ref.filename}",
            digest=digest_of(destination / ref.filename),
            size=(destination / ref.filename).stat().st_size,
            collector=PRICES,
            collector_version=PRICE_VERSION,
            game_version=version,
            upstream=run.prices_url,
        )
        for ref in sorted(
            harvest.fetched + harvest.skipped, key=lambda ref: ref.snapshot_date
        )
    ]
    return CollectorReport(
        collector=PRICES,
        files=tuple(staged),
        notes=(f"{len(harvest.fetched)} newly fetched, {harvest.available} in all",),
    )


COLLECTORS: Final[dict[str, Callable[[StagingRun, GameVersion], CollectorReport]]] = {
    CONFIGS: stage_configs,
    TABLES: stage_tables,
    PRICES: stage_prices,
}


def stage(run: StagingRun, only: Sequence[str] = ()) -> StagingReport:
    """Run the named collectors, or all of them, and rewrite the manifest."""
    chosen = _chosen(only)
    version = game_version_of(run.checkout, GAME_REPO)
    manifest = read_manifest_if_staged(run.destination) or StagingManifest(
        staged_at=datetime.now(tz=UTC)
    )
    reports: list[CollectorReport] = []
    for name in chosen:
        report = COLLECTORS[name](run, version)
        manifest = manifest.replacing(name, report.files)
        reports.append(report)
    write_manifest(
        run.destination,
        manifest.model_copy(update={"staged_at": datetime.now(tz=UTC)}),
    )
    return StagingReport(
        destination=str(run.destination),
        game_version=str(version),
        reports=tuple(reports),
    )


def _chosen(only: Sequence[str]) -> tuple[str, ...]:
    if not only:
        return tuple(COLLECTORS)
    for name in only:
        if name not in COLLECTORS:
            raise UnknownCollector(name, tuple(COLLECTORS))
    return tuple(name for name in COLLECTORS if name in set(only))


def _as_json(payload: object) -> bytes:
    return (
        json.dumps(payload, indent=JSON_INDENT, sort_keys=False, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _write(
    target: Path,
    payload: bytes,
    *,
    collector: str,
    version: int,
    game_version: GameVersion,
    upstream: str,
    relative: str,
) -> StagedFile:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + PARTIAL_SUFFIX)
    partial.write_bytes(payload)
    partial.replace(target)
    return StagedFile(
        path=relative,
        digest=digest_of(target),
        size=target.stat().st_size,
        collector=collector,
        collector_version=version,
        game_version=game_version,
        upstream=upstream,
    )


# test cases


def _declaration(enum: str, filename: str) -> str:
    if filename.endswith(".kt"):
        return f'enum class {enum}(val label: String) {{ ONE("first"), TWO("second") }}'
    return (
        f"public enum {enum} {{ "
        'ONE("first"), TWO("second"); '
        f"private {enum}(String label) {{ }} }}"
    )


def _checkout(tmp_path: Path) -> StagingRun:
    import subprocess

    checkout = tmp_path / "game_data" / GAME_CHECKOUT
    (checkout / "Server/data/configs").mkdir(parents=True)
    (checkout / "Server/src/main/content/data").mkdir(parents=True)
    for config in DECLARED_CONFIGS:
        (checkout / config.upstream).write_text("[]", encoding="utf-8")
    for table in DECLARED_TABLES:
        path = checkout / table.upstream
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_declaration(table.enum, table.filename), encoding="utf-8")
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.email", "test@example.test"),
        ("config", "user.name", "test"),
        ("add", "-A"),
        ("commit", "--quiet", "-m", "sources"),
    ):
        subprocess.run(["git", "-C", str(checkout), *arguments], check=True)
    return StagingRun(
        game_data=tmp_path / "game_data",
        destination=tmp_path / "data" / "source",
        prices_url="https://example.test/gedata/",
    )


def test_staging_copies_the_configs_and_reads_the_tables(tmp_path: Path) -> None:
    run = _checkout(tmp_path)
    report = stage(run, only=[CONFIGS, TABLES])
    assert report.count == len(DECLARED_CONFIGS) + len(DECLARED_TABLES)
    assert (run.destination / "configs/item_configs.json").read_text() == "[]"
    table = json.loads((run.destination / "tables/Quests.json").read_text())
    assert table["enum"] == "Quests"
    assert [row["name"] for row in table["constants"]] == ["ONE", "TWO"]


def test_a_staging_run_writes_a_manifest_that_matches_what_it_wrote(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.staging.manifest import read_manifest

    run = _checkout(tmp_path)
    stage(run, only=[CONFIGS])
    manifest = read_manifest(run.destination)
    assert manifest.drifted(run.destination) == ()
    entry = manifest.entry("configs/item_configs.json")
    assert entry.collector == CONFIGS
    assert entry.upstream is not None
    assert entry.upstream.endswith("item_configs.json")
    assert entry.game_version.repo == GAME_REPO


def test_staging_one_collector_leaves_another_ones_files_listed(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.staging.manifest import read_manifest

    run = _checkout(tmp_path)
    stage(run, only=[CONFIGS, TABLES])
    stage(run, only=[TABLES])
    manifest = read_manifest(run.destination)
    assert manifest.by_collector(CONFIGS)
    assert manifest.by_collector(TABLES)


def test_staging_twice_writes_the_same_bytes(tmp_path: Path) -> None:
    run = _checkout(tmp_path)
    stage(run, only=[CONFIGS, TABLES])
    first = (run.destination / "tables/Quests.json").read_bytes()
    stage(run, only=[CONFIGS, TABLES])
    assert (run.destination / "tables/Quests.json").read_bytes() == first


def test_an_edit_to_a_staged_file_shows_up_against_the_manifest(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.staging.manifest import read_manifest

    run = _checkout(tmp_path)
    stage(run, only=[CONFIGS])
    (run.destination / "configs/item_configs.json").write_text("[1]", encoding="utf-8")
    manifest = read_manifest(run.destination)
    assert manifest.drifted(run.destination) == ("configs/item_configs.json",)


def test_a_missing_upstream_file_names_the_collector_and_the_path(
    tmp_path: Path,
) -> None:
    import pytest

    run = _checkout(tmp_path)
    (run.checkout / DECLARED_CONFIGS[0].upstream).unlink()
    with pytest.raises(UpstreamMissing) as caught:
        stage(run, only=[CONFIGS])
    assert CONFIGS in str(caught.value)
    assert DECLARED_CONFIGS[0].name in str(caught.value)


def test_asking_for_a_collector_nobody_declares_is_refused(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(UnknownCollector):
        stage(_checkout(tmp_path), only=["images"])


def test_a_report_says_what_each_collector_did(tmp_path: Path) -> None:
    report = stage(_checkout(tmp_path), only=[TABLES])
    told = "\n".join(report.lines())
    assert "tables: " in told
    assert "Quests: 2 rows" in told
