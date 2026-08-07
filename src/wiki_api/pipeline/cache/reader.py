"""Open a game cache and hand out the files inside it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from wiki_api.pipeline.cache.containers import (
    CONTAINER_HEADER,
    REFERENCE_INDEX,
    CacheStore,
    split_archive,
    unpack,
)
from wiki_api.pipeline.cache.errors import ArchiveUnreadable
from wiki_api.pipeline.cache.reference import ReferenceTable, read_reference
from wiki_api.pipeline.cache.xtea import decrypt

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

ITEM_INDEX: Final = 19
SCENERY_INDEX: Final = 16
NPC_INDEX: Final = 18
MAP_INDEX: Final = 5
DEFINITION_INDEXES: Final = (ITEM_INDEX, SCENERY_INDEX, NPC_INDEX)
DEFINITIONS_PER_ARCHIVE: Final = 256


class CacheReader:
    """One open cache, reading a file at a time out of the indexes it was opened for."""

    def __init__(self, store: CacheStore, tables: Mapping[int, ReferenceTable]) -> None:
        self._store = store
        self._tables = tables

    @classmethod
    def at(
        cls, directory: Path, indexes: tuple[int, ...] = DEFINITION_INDEXES
    ) -> CacheReader:
        """Open the cache in a directory, reading the reference table of each index."""
        store = CacheStore.at(directory, indexes)
        tables: dict[int, ReferenceTable] = {}
        for index in indexes:
            packed = store.container(REFERENCE_INDEX, index)
            if packed is None:
                raise ArchiveUnreadable(REFERENCE_INDEX, index, "no reference table")
            tables[index] = read_reference(
                index, unpack(REFERENCE_INDEX, index, packed)
            )
        return cls(store, tables)

    @property
    def indexes(self) -> tuple[int, ...]:
        return tuple(sorted(self._tables))

    def table(self, index: int) -> ReferenceTable:
        """The reference table of one index, which carries its revision."""
        return self._tables[index]

    def archive(
        self, index: int, archive: int, keys: tuple[int, ...] | None = None
    ) -> tuple[bytes, ...]:
        """Every file in one archive, in the order the reference table lists them."""
        packed = self._store.container(index, archive)
        if packed is None:
            raise ArchiveUnreadable(index, archive, "the index has no entry")
        if keys is not None:
            packed = decrypt(keys, packed, CONTAINER_HEADER)
        data = unpack(index, archive, packed)
        return split_archive(
            index, archive, data, len(self._tables[index].files[archive])
        )

    def definitions(self, index: int) -> tuple[tuple[int, bytes], ...]:
        """Every definition in an index, keyed by the id the game addresses it with."""
        table = self._tables[index]
        read: list[tuple[int, bytes]] = []
        for archive in table.archives:
            files = self.archive(index, archive)
            for position, file_id in enumerate(table.files[archive]):
                read.append(
                    (archive * DEFINITIONS_PER_ARCHIVE + file_id, files[position])
                )
        return tuple(read)


# test cases


def test_a_cache_opens_and_reads_the_definition_inside_it(tmp_path: Path) -> None:
    from tests.cache import built_cache

    reader = CacheReader.at(built_cache(tmp_path / "cache"), indexes=(ITEM_INDEX,))
    assert reader.indexes == (ITEM_INDEX,)
    assert reader.table(ITEM_INDEX).revision == 214
    read = reader.definitions(ITEM_INDEX)
    assert len(read) == 1
    identity, body = read[0]
    assert identity == 17 * DEFINITIONS_PER_ARCHIVE + 235
    assert b"Dragon scimitar" in body


def test_a_cache_directory_with_no_data_file_is_refused(tmp_path: Path) -> None:
    import pytest

    from wiki_api.pipeline.cache.errors import CacheMissing

    with pytest.raises(CacheMissing):
        CacheReader.at(tmp_path / "nothing", indexes=(ITEM_INDEX,))


def test_an_index_with_no_file_is_named(tmp_path: Path) -> None:
    import pytest
    from tests.cache import built_cache

    from wiki_api.pipeline.cache.errors import IndexMissing

    with pytest.raises(IndexMissing):
        CacheReader.at(built_cache(tmp_path / "cache"), indexes=(ITEM_INDEX, 12))


def test_every_index_a_reader_opens_answers_for_its_own_archives(
    tmp_path: Path,
) -> None:
    from tests.cache import built_cache

    reader = CacheReader.at(
        built_cache(tmp_path / "cache"),
        indexes=(ITEM_INDEX, SCENERY_INDEX, NPC_INDEX, MAP_INDEX),
    )
    assert reader.indexes == (MAP_INDEX, SCENERY_INDEX, NPC_INDEX, ITEM_INDEX)
    assert len(reader.definitions(SCENERY_INDEX)) == 1
    assert reader.table(MAP_INDEX).archive_named("l50_50") == 0


def test_an_archive_the_index_does_not_list_is_named(tmp_path: Path) -> None:
    import pytest
    from tests.cache import built_cache

    from wiki_api.pipeline.cache.errors import ArchiveUnreadable

    reader = CacheReader.at(built_cache(tmp_path / "cache"), indexes=(ITEM_INDEX,))
    with pytest.raises(ArchiveUnreadable):
        reader.archive(ITEM_INDEX, 99)
