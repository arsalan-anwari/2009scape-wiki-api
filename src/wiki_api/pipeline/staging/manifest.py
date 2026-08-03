"""What the staged sources say about themselves, and whether they still match."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Final, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from wiki_api.domain.provenance import GameVersion
from wiki_api.pipeline.staging.errors import (
    ManifestMissing,
    ManifestSchemaMismatch,
    StagedFileMissing,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

MANIFEST_SCHEMA: Final = 1
MANIFEST_NAME: Final = "sources.json"
READ_CHUNK: Final = 1 << 20


class StagedFile(BaseModel):
    """One staged file, and what it was made from."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    size: int = Field(ge=0)
    collector: str = Field(min_length=1)
    collector_version: int = Field(ge=1)
    game_version: GameVersion
    upstream: str | None = None


class StagingManifest(BaseModel):
    """Every staged file, written beside them so a build can check what it reads."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    schema_version: int = Field(default=MANIFEST_SCHEMA, alias="schema")
    staged_at: AwareDatetime
    files: tuple[StagedFile, ...] = ()

    def by_collector(self, collector: str) -> tuple[StagedFile, ...]:
        """Every file one collector staged."""
        return tuple(entry for entry in self.files if entry.collector == collector)

    def paths_under(self, prefix: str) -> tuple[str, ...]:
        """The staged paths inside one directory, in a stable order."""
        return tuple(
            sorted(entry.path for entry in self.files if entry.path.startswith(prefix))
        )

    def entry(self, path: str) -> StagedFile:
        """The manifest line for one staged path."""
        for candidate in self.files:
            if candidate.path == path:
                return candidate
        raise StagedFileMissing(path)

    def replacing(self, collector: str, staged: Iterable[StagedFile]) -> Self:
        """A manifest with one collector's files swapped for the ones just written."""
        kept = [entry for entry in self.files if entry.collector != collector]
        return self.model_copy(update={"files": _ordered([*kept, *staged])}, deep=False)

    def drifted(self, root: Path) -> tuple[str, ...]:
        """The staged paths whose bytes no longer match what was staged."""
        changed: list[str] = []
        for entry in self.files:
            target = root / entry.path
            if not target.is_file() or digest_of(target) != entry.digest:
                changed.append(entry.path)
        return tuple(changed)


def _ordered(files: Iterable[StagedFile]) -> tuple[StagedFile, ...]:
    return tuple(sorted(files, key=lambda entry: entry.path))


def digest_of(path: Path) -> str:
    """Hash one file's bytes without reading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(READ_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(root: Path) -> Path:
    """Where the manifest sits inside a staged directory."""
    return root / MANIFEST_NAME


def read_manifest(root: Path) -> StagingManifest:
    """Read the manifest, refusing one written by a different staging schema."""
    path = manifest_path(root)
    if not path.is_file():
        raise ManifestMissing(str(path))
    manifest = StagingManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.schema_version != MANIFEST_SCHEMA:
        raise ManifestSchemaMismatch(manifest.schema_version, MANIFEST_SCHEMA)
    return manifest


def read_manifest_if_staged(root: Path) -> StagingManifest | None:
    """The manifest if there is one, so a first staging run has something to add to."""
    if not manifest_path(root).is_file():
        return None
    return read_manifest(root)


def write_manifest(root: Path, manifest: StagingManifest) -> Path:
    """Write the manifest out, sorted, so two stagings of one tree compare cleanly."""
    root.mkdir(parents=True, exist_ok=True)
    path = manifest_path(root)
    ordered = manifest.model_copy(update={"files": _ordered(manifest.files)})
    path.write_text(
        ordered.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8"
    )
    return path


# test cases


def _entry(path: str, collector: str = "configs", digest: str = "a") -> StagedFile:
    return StagedFile(
        path=path,
        digest=digest,
        size=1,
        collector=collector,
        collector_version=1,
        game_version=GameVersion.model_validate("2009scape@1f4a2c9"),
        upstream=None,
    )


def _manifest(*files: StagedFile) -> StagingManifest:
    from datetime import UTC, datetime

    return StagingManifest(
        staged_at=datetime(2026, 8, 3, tzinfo=UTC),
        files=files,
    )


def test_a_digest_is_the_sha256_of_the_bytes(tmp_path: Path) -> None:
    written = tmp_path / "one.json"
    written.write_bytes(b"{}")
    assert digest_of(written) == hashlib.sha256(b"{}").hexdigest()


def test_a_manifest_round_trips_through_the_file_it_is_written_to(
    tmp_path: Path,
) -> None:
    manifest = _manifest(_entry("configs/item_configs.json"))
    write_manifest(tmp_path, manifest)
    assert read_manifest(tmp_path) == manifest


def test_a_manifest_is_written_in_a_stable_order(tmp_path: Path) -> None:
    write_manifest(tmp_path, _manifest(_entry("b.json"), _entry("a.json")))
    assert [entry.path for entry in read_manifest(tmp_path).files] == [
        "a.json",
        "b.json",
    ]


def test_staging_one_collector_again_leaves_the_others_alone() -> None:
    manifest = _manifest(
        _entry("configs/items.json", "configs"),
        _entry("tables/Quests.json", "tables"),
    )
    replaced = manifest.replacing("tables", [_entry("tables/Bars.json", "tables")])
    assert [entry.path for entry in replaced.files] == [
        "configs/items.json",
        "tables/Bars.json",
    ]


def test_a_manifest_says_which_files_one_collector_staged() -> None:
    manifest = _manifest(
        _entry("configs/items.json", "configs"),
        _entry("tables/Quests.json", "tables"),
    )
    assert [entry.path for entry in manifest.by_collector("tables")] == [
        "tables/Quests.json"
    ]
    assert manifest.paths_under("configs/") == ("configs/items.json",)


def test_a_file_edited_after_staging_is_reported_as_drifted(tmp_path: Path) -> None:
    staged = tmp_path / "configs"
    staged.mkdir()
    written = staged / "items.json"
    written.write_text("[]", encoding="utf-8")
    manifest = _manifest(_entry("configs/items.json", digest=digest_of(written)))
    assert manifest.drifted(tmp_path) == ()
    written.write_text("[1]", encoding="utf-8")
    assert manifest.drifted(tmp_path) == ("configs/items.json",)


def test_a_file_the_manifest_lists_and_nobody_staged_counts_as_drifted(
    tmp_path: Path,
) -> None:
    assert _manifest(_entry("configs/gone.json")).drifted(tmp_path) == (
        "configs/gone.json",
    )


def test_asking_for_a_path_nothing_staged_is_refused() -> None:
    import pytest

    with pytest.raises(StagedFileMissing):
        _manifest().entry("configs/items.json")


def test_reading_a_directory_nobody_staged_is_refused(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ManifestMissing):
        read_manifest(tmp_path)
    assert read_manifest_if_staged(tmp_path) is None


def test_a_manifest_from_another_schema_is_refused(tmp_path: Path) -> None:
    import pytest

    manifest_path(tmp_path).write_text(
        _manifest().model_dump_json(by_alias=True).replace('"schema":1', '"schema":2'),
        encoding="utf-8",
    )
    with pytest.raises(ManifestSchemaMismatch):
        read_manifest(tmp_path)
