from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tests.conftest import build_fixture_artifact
from wiki_api.pipeline.artifact import content_hash

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.pipeline.artifact import KnowledgeSnapshot

LATER = datetime(2026, 8, 1, 9, 30, tzinfo=UTC)


def test_the_same_inputs_produce_an_identical_artifact(tmp_path: Path) -> None:
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    first_manifest = build_fixture_artifact(first)
    second_manifest = build_fixture_artifact(second)
    assert first_manifest.content_hash == second_manifest.content_hash
    assert first.read_bytes() == second.read_bytes()


def test_rebuilding_over_an_existing_artifact_is_identical(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    build_fixture_artifact(destination)
    first = destination.read_bytes()
    build_fixture_artifact(destination)
    assert destination.read_bytes() == first


def test_the_content_hash_ignores_when_the_build_ran(tmp_path: Path) -> None:
    first = build_fixture_artifact(tmp_path / "first.sqlite3")
    second = build_fixture_artifact(tmp_path / "second.sqlite3", built_at=LATER)
    assert first.content_hash == second.content_hash
    assert first.built_at != second.built_at


def test_a_different_build_clock_still_changes_the_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    build_fixture_artifact(first)
    build_fixture_artifact(second, built_at=LATER)
    assert first.read_bytes() != second.read_bytes()


def test_the_content_hash_covers_the_knowledge_itself(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    from wiki_api.pipeline.artifact import KnowledgeSnapshot as Snapshot

    trimmed = Snapshot(
        entities=fixture_snapshot.entities[:-1],
        edges=fixture_snapshot.edges,
        aliases=fixture_snapshot.aliases,
        prices=fixture_snapshot.prices,
    )
    assert content_hash(trimmed) != content_hash(fixture_snapshot)


def test_the_data_version_is_recorded_without_touching_the_content_hash(
    tmp_path: Path,
) -> None:
    first = build_fixture_artifact(tmp_path / "first.sqlite3", data_version="a")
    second = build_fixture_artifact(tmp_path / "second.sqlite3", data_version="b")
    assert first.data_version != second.data_version
    assert first.content_hash == second.content_hash
