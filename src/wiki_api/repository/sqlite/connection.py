"""Handing out read only SQLite connections, one per thread."""

from __future__ import annotations

import sqlite3
import threading
from typing import TYPE_CHECKING

from wiki_api.repository.errors import ArtifactUnavailable

if TYPE_CHECKING:
    from pathlib import Path


class ReadOnlyConnections:
    """A pool of connections to one artifact, opened read only and never written to."""

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise ArtifactUnavailable(path)
        self._path = path
        self._uri = f"file:{path}?mode=ro&immutable=1"
        self._local = threading.local()
        self._opened: list[sqlite3.Connection] = []
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> sqlite3.Connection:
        existing: sqlite3.Connection | None = getattr(self._local, "connection", None)
        if existing is not None:
            return existing
        connection = sqlite3.connect(self._uri, uri=True, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        self._local.connection = connection
        with self._lock:
            self._opened.append(connection)
        return connection

    def close(self) -> None:
        with self._lock:
            opened, self._opened = self._opened, []
        for connection in opened:
            connection.close()
        self._local = threading.local()


# test cases


def test_a_missing_artifact_is_reported_before_any_query(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ArtifactUnavailable):
        ReadOnlyConnections(tmp_path / "absent.sqlite3")


def test_connections_are_reused_per_thread(tmp_path: Path) -> None:
    path = _artifact(tmp_path)
    connections = ReadOnlyConnections(path)
    try:
        assert connections.get() is connections.get()
    finally:
        connections.close()


def test_each_thread_gets_its_own_connection(tmp_path: Path) -> None:
    path = _artifact(tmp_path)
    connections = ReadOnlyConnections(path)
    seen: list[int] = []

    def record() -> None:
        seen.append(id(connections.get()))

    try:
        worker = threading.Thread(target=record)
        worker.start()
        worker.join()
        record()
        assert len(set(seen)) == 2
    finally:
        connections.close()


def test_the_artifact_is_opened_read_only(tmp_path: Path) -> None:
    import pytest

    path = _artifact(tmp_path)
    connections = ReadOnlyConnections(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connections.get().execute("CREATE TABLE intruder (id INTEGER)")
    finally:
        connections.close()


def _artifact(directory: Path) -> Path:
    path = directory / "artifact.sqlite3"
    seed = sqlite3.connect(path)
    try:
        seed.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY)")
        seed.commit()
    finally:
        seed.close()
    return path
