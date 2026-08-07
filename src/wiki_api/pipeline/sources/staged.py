"""Read the staged sources, and nothing outside them."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from wiki_api.pipeline.enums.reader import EnumTable
from wiki_api.pipeline.staging.collectors import PRICES
from wiki_api.pipeline.staging.declared import (
    DeclaredConfig,
    DeclaredExtract,
    DeclaredTable,
)
from wiki_api.pipeline.staging.errors import StagedFileMissing
from wiki_api.pipeline.staging.manifest import StagingManifest, read_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.domain.provenance import GameVersion


@dataclass(frozen=True)
class StagedSources:
    """A staged directory together with the manifest that describes it."""

    root: Path
    manifest: StagingManifest

    @classmethod
    def at(cls, root: Path) -> StagedSources:
        return cls(root=root, manifest=read_manifest(root))

    def path(self, staged: str) -> Path:
        target = self.root / self.manifest.entry(staged).path
        if not target.is_file():
            raise StagedFileMissing(staged)
        return target

    def game_version(self, staged: str) -> GameVersion:
        return self.manifest.entry(staged).game_version

    def records(self, declared: DeclaredConfig) -> tuple[dict[str, Any], ...]:
        """Read one staged config file as the list of records it holds."""
        payload = json.loads(self.path(declared.staged).read_text(encoding="utf-8"))
        return tuple(payload)

    def table(self, declared: DeclaredTable) -> EnumTable:
        """Read one staged enum table."""
        return EnumTable.model_validate_json(
            self.path(declared.staged).read_text(encoding="utf-8")
        )

    def extract(self, declared: DeclaredExtract) -> tuple[dict[str, Any], ...]:
        """Read one staged cache extract as the records it holds."""
        path = self.path(declared.staged)
        if not declared.compressed:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return tuple(payload)
        import gzip

        lines = gzip.decompress(path.read_bytes()).decode("utf-8").splitlines()
        return tuple(json.loads(line) for line in lines if line)

    def has_extract(self, declared: DeclaredExtract) -> bool:
        """Whether a cache extract was staged, so a build can say it was not."""
        try:
            self.path(declared.staged)
        except StagedFileMissing:
            return False
        return True

    def revision(self, staged: str) -> str | None:
        """What the manifest records about the revision of one staged file."""
        return self.manifest.entry(staged).source_revision

    def price_files(self) -> tuple[Path, ...]:
        """Every staged price snapshot, oldest first."""
        return tuple(
            self.root / entry.path
            for entry in sorted(
                self.manifest.by_collector(PRICES), key=lambda entry: entry.path
            )
        )

    def drifted(self) -> tuple[str, ...]:
        """The staged files whose bytes no longer match what was staged."""
        return self.manifest.drifted(self.root)


# test cases


def _staged(tmp_path: Path) -> StagedSources:
    from datetime import UTC, datetime

    from wiki_api.domain.provenance import GameVersion
    from wiki_api.pipeline.staging.manifest import (
        StagedFile,
        digest_of,
        write_manifest,
    )

    (tmp_path / "configs").mkdir(parents=True)
    (tmp_path / "tables").mkdir(parents=True)
    (tmp_path / "grand-exchange").mkdir(parents=True)
    written = {
        "configs/item_configs.json": '[{"id": "4587", "name": "Dragon scimitar"}]',
        "tables/Quests.json": EnumTable(
            enum="Quests",
            source_file="Quests.kt",
            language="kotlin",  # type: ignore[arg-type]
        ).model_dump_json(),
        "grand-exchange/2024-06-08.json": '[{"item_id": 4587, "value": 106049}]',
        "grand-exchange/2026-07-25.json": '[{"item_id": 4587, "value": 108590}]',
    }
    for name, payload in written.items():
        (tmp_path / name).write_text(payload, encoding="utf-8")
    write_manifest(
        tmp_path,
        StagingManifest(
            staged_at=datetime(2026, 8, 3, tzinfo=UTC),
            files=tuple(
                StagedFile(
                    path=name,
                    digest=digest_of(tmp_path / name),
                    size=(tmp_path / name).stat().st_size,
                    collector=PRICES if name.startswith("grand") else "configs",
                    collector_version=1,
                    game_version=GameVersion.model_validate("2009scape@1f4a2c9"),
                    upstream=None,
                )
                for name in written
            ),
        ),
    )
    return StagedSources.at(tmp_path)


def test_a_staged_config_reads_back_as_records(tmp_path: Path) -> None:
    staged = _staged(tmp_path)
    records = staged.records(DeclaredConfig(name="item_configs.json"))
    assert records[0]["name"] == "Dragon scimitar"


def test_a_staged_table_reads_back_as_a_table(tmp_path: Path) -> None:
    staged = _staged(tmp_path)
    table = staged.table(DeclaredTable(enum="Quests", path="content/data/Quests.kt"))
    assert table.enum == "Quests"


def test_the_price_snapshots_come_back_oldest_first(tmp_path: Path) -> None:
    staged = _staged(tmp_path)
    assert [path.name for path in staged.price_files()] == [
        "2024-06-08.json",
        "2026-07-25.json",
    ]


def test_every_fact_can_name_the_commit_behind_the_file_it_came_from(
    tmp_path: Path,
) -> None:
    staged = _staged(tmp_path)
    assert staged.game_version("configs/item_configs.json").commit == "1f4a2c9"


def test_a_source_nobody_staged_is_refused(tmp_path: Path) -> None:
    import pytest

    staged = _staged(tmp_path)
    with pytest.raises(StagedFileMissing):
        staged.records(DeclaredConfig(name="npc_configs.json"))


def test_a_staged_file_deleted_after_staging_is_refused(tmp_path: Path) -> None:
    import pytest

    staged = _staged(tmp_path)
    (tmp_path / "configs/item_configs.json").unlink()
    with pytest.raises(StagedFileMissing):
        staged.path("configs/item_configs.json")


def test_a_staged_cache_extract_reads_back_as_records(tmp_path: Path) -> None:
    from tests.sources import staged_from

    from wiki_api.pipeline.staging.declared import ITEM_EXTRACT

    staged = staged_from(
        tmp_path,
        {ITEM_EXTRACT.staged: '[{"id": 4587, "value": 100000}]'},
        revisions={ITEM_EXTRACT.staged: "index 19 revision 214"},
    )
    assert staged.extract(ITEM_EXTRACT)[0]["value"] == 100000
    assert staged.has_extract(ITEM_EXTRACT) is True
    assert staged.revision(ITEM_EXTRACT.staged) == "index 19 revision 214"


def test_a_compressed_extract_reads_one_record_per_line(tmp_path: Path) -> None:
    import gzip

    from tests.sources import staged_from

    from wiki_api.pipeline.staging.declared import PLACEMENT_EXTRACT

    staged = staged_from(
        tmp_path,
        {
            PLACEMENT_EXTRACT.staged: gzip.compress(
                b'{"region": 12850}\n{"region": 12851}\n'
            )
        },
    )
    read = staged.extract(PLACEMENT_EXTRACT)
    assert [record["region"] for record in read] == [12850, 12851]


def test_a_cache_extract_nobody_staged_is_absent_rather_than_an_error(
    tmp_path: Path,
) -> None:
    from tests.sources import staged_from

    from wiki_api.pipeline.staging.declared import ITEM_EXTRACT

    staged = staged_from(tmp_path, {"configs/item_configs.json": "[]"})
    assert staged.has_extract(ITEM_EXTRACT) is False


def test_an_edit_after_staging_is_visible_to_the_build(tmp_path: Path) -> None:
    staged = _staged(tmp_path)
    assert staged.drifted() == ()
    (tmp_path / "configs/item_configs.json").write_text("[]", encoding="utf-8")
    assert StagedSources.at(tmp_path).drifted() == ("configs/item_configs.json",)
