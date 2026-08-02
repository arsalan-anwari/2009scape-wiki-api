"""Build the artifact the suite reads, in a place a person can open too."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from wiki_api.pipeline.artifact import build_snapshot, write_artifact

if TYPE_CHECKING:
    from wiki_api.domain.manifest import Manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_KNOWLEDGE = Path(__file__).parent / "fixtures" / "knowledge"
FIXTURE_DATA_VERSION = "fixture-0001"
FIXTURE_GAME_VERSION = "2009scape@5a37f2f8"
FIXTURE_BUILT_AT = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
TEST_ARTIFACT = REPO_ROOT / "data" / "tests" / "knowledge.sqlite3"


def build_fixture_artifact(
    destination: Path,
    *,
    data_version: str = FIXTURE_DATA_VERSION,
    built_at: datetime = FIXTURE_BUILT_AT,
) -> Manifest:
    """Write the hand-made documents out as an artifact at this path."""
    return write_artifact(
        build_snapshot(FIXTURE_KNOWLEDGE),
        destination,
        data_version=data_version,
        game_version=FIXTURE_GAME_VERSION,
        built_at=built_at,
    )


def build_test_artifact() -> Manifest:
    """Rebuild the artifact the suite reads, replacing whatever was there before.

    Written beside the real dataset, never over it, and under a temporary name so a
    reader never opens a half-finished database.
    """
    staged = TEST_ARTIFACT.with_name(TEST_ARTIFACT.name + ".building")
    try:
        manifest = build_fixture_artifact(staged)
        os.replace(staged, TEST_ARTIFACT)
    finally:
        staged.unlink(missing_ok=True)
    return manifest


def main() -> None:
    """Build the test artifact and say where it went."""
    manifest = build_test_artifact()
    print(f"built {manifest.data_version} at {TEST_ARTIFACT} ({manifest.content_hash})")


if __name__ == "__main__":
    main()


# test cases


def test_the_test_dataset_never_lands_where_a_deployment_reads() -> None:
    assert TEST_ARTIFACT.parent.name == "tests"
    assert TEST_ARTIFACT.parent.parent.name == "data"
    assert TEST_ARTIFACT.parent != TEST_ARTIFACT.parent.parent


def test_what_it_builds_is_the_hand_made_documents() -> None:
    assert FIXTURE_KNOWLEDGE.is_dir()
    assert any(FIXTURE_KNOWLEDGE.glob("*.json"))


def test_a_rebuild_replaces_the_dataset_rather_than_adding_to_it() -> None:
    first = build_test_artifact()
    size = TEST_ARTIFACT.stat().st_size
    second = build_test_artifact()
    assert first.content_hash == second.content_hash
    assert TEST_ARTIFACT.stat().st_size == size


def test_a_finished_build_leaves_nothing_half_written_behind() -> None:
    build_test_artifact()
    staged = TEST_ARTIFACT.with_name(TEST_ARTIFACT.name + ".building")
    assert not staged.exists()
