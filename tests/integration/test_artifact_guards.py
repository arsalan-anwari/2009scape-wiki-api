from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING

import pytest

from tests.conftest import build_fixture_artifact
from wiki_api.domain.errors import IncompatibleArtifact
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.manifest import SCHEMA_VERSION
from wiki_api.repository.errors import ArtifactUnavailable, ArtifactUnreadable
from wiki_api.repository.sqlite import SqliteKnowledgeRepository

if TYPE_CHECKING:
    from pathlib import Path


def test_an_artifact_from_a_newer_schema_is_refused(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    build_fixture_artifact(destination)
    _set_schema_version(destination, SCHEMA_VERSION + 1)
    with pytest.raises(IncompatibleArtifact) as raised:
        SqliteKnowledgeRepository(destination)
    assert raised.value.found == SCHEMA_VERSION + 1
    assert raised.value.expected == SCHEMA_VERSION


def test_an_artifact_without_a_manifest_is_refused(tmp_path: Path) -> None:
    destination = tmp_path / "knowledge.sqlite3"
    build_fixture_artifact(destination)
    connection = sqlite3.connect(destination)
    try:
        connection.execute("DELETE FROM meta")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(IncompatibleArtifact):
        SqliteKnowledgeRepository(destination)


def test_a_missing_artifact_is_reported_before_any_query(tmp_path: Path) -> None:
    with pytest.raises(ArtifactUnavailable):
        SqliteKnowledgeRepository(tmp_path / "absent.sqlite3")


def test_a_file_that_is_not_an_artifact_is_reported(tmp_path: Path) -> None:
    impostor = tmp_path / "knowledge.sqlite3"
    impostor.write_text("this is not a database", encoding="utf-8")
    with pytest.raises(ArtifactUnreadable):
        SqliteKnowledgeRepository(impostor)


def test_an_empty_database_is_reported(tmp_path: Path) -> None:
    empty = tmp_path / "empty.sqlite3"
    connection = sqlite3.connect(empty)
    connection.close()
    with pytest.raises(ArtifactUnreadable):
        SqliteKnowledgeRepository(empty)


def test_a_full_read_workload_leaves_the_artifact_untouched(
    fixture_artifact: Path,
) -> None:
    before = fixture_artifact.read_bytes()
    repository = SqliteKnowledgeRepository(fixture_artifact)
    try:
        repository.search("dragon", limit=50)
        repository.list_entities(EntityType.ITEM, limit=50)
        repository.get_entity(EntityKey(type=EntityType.ITEM, id=4587))
        repository.edges_from((EntityKey(type=EntityType.NPC, id=50),))
        repository.price_history(4587)
    finally:
        repository.close()
    assert fixture_artifact.read_bytes() == before
    assert not list(fixture_artifact.parent.glob("*.sqlite3-journal"))


def test_the_repository_serves_several_threads(fixture_artifact: Path) -> None:
    repository = SqliteKnowledgeRepository(fixture_artifact)
    names: list[str] = []
    errors: list[BaseException] = []

    def read() -> None:
        try:
            key = EntityKey(type=EntityType.ITEM, id=4587)
            names.append(repository.get_entity(key).name)
        except BaseException as error:
            errors.append(error)

    try:
        workers = [threading.Thread(target=read) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    finally:
        repository.close()
    assert not errors
    assert names == ["Dragon scimitar"] * 8


def test_a_closed_repository_can_be_reopened(fixture_artifact: Path) -> None:
    repository = SqliteKnowledgeRepository(fixture_artifact)
    repository.close()
    reopened = SqliteKnowledgeRepository(fixture_artifact)
    try:
        assert reopened.manifest().is_readable is True
    finally:
        reopened.close()


def _set_schema_version(destination: Path, version: int) -> None:
    connection = sqlite3.connect(destination)
    try:
        connection.execute(
            "UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(version),)
        )
        connection.commit()
    finally:
        connection.close()
