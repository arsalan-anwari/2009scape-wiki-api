"""Walk the cache's sectors and unpack the containers they hold."""

from __future__ import annotations

import bz2
import gzip
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from wiki_api.pipeline.cache.errors import (
    ArchiveUnreadable,
    CacheMissing,
    IndexMissing,
    MalformedContainer,
)

if TYPE_CHECKING:
    from pathlib import Path

DATA_FILE: Final = "main_file_cache.dat2"
INDEX_FILE: Final = "main_file_cache.idx{index}"
REFERENCE_INDEX: Final = 255
SECTOR_SIZE: Final = 520
SECTOR_HEADER: Final = 8
SECTOR_PAYLOAD: Final = SECTOR_SIZE - SECTOR_HEADER
ENTRY_SIZE: Final = 6
CONTAINER_HEADER: Final = 5
NO_COMPRESSION: Final = 0
BZIP2: Final = 1
BZIP2_MAGIC: Final = b"BZh1"
MAX_CONTAINER: Final = 5_000_000
MAX_UNPACKED: Final = 20_000_000


@dataclass(frozen=True)
class CacheStore:
    """The cache's data file and the index files that point into it."""

    directory: Path
    data: bytes
    indexes: dict[int, bytes]

    @classmethod
    def at(cls, directory: Path, indexes: tuple[int, ...]) -> CacheStore:
        """Read the data file and the named index files into memory."""
        data_path = directory / DATA_FILE
        if not data_path.is_file():
            raise CacheMissing(str(directory))
        wanted = (*indexes, REFERENCE_INDEX)
        read: dict[int, bytes] = {}
        for index in wanted:
            path = directory / INDEX_FILE.format(index=index)
            if not path.is_file():
                raise IndexMissing(index, str(path))
            read[index] = path.read_bytes()
        return cls(directory=directory, data=data_path.read_bytes(), indexes=read)

    def container(self, index: int, container: int) -> bytes | None:
        """The packed bytes of one container, or nothing where the index has none."""
        entries = self.indexes[index]
        at = ENTRY_SIZE * container
        if len(entries) < at + ENTRY_SIZE:
            return None
        size = (entries[at] << 16) | (entries[at + 1] << 8) | entries[at + 2]
        sector = (entries[at + 3] << 16) | (entries[at + 4] << 8) | entries[at + 5]
        if size < 0 or size > MAX_CONTAINER:
            raise MalformedContainer(index, container, f"declares {size} bytes")
        if sector <= 0 or len(self.data) // SECTOR_SIZE < sector:
            return None
        return self._walk(index, container, size, sector)

    def _walk(self, index: int, container: int, size: int, sector: int) -> bytes:
        out = bytearray()
        part = 0
        while len(out) < size:
            if sector == 0:
                raise MalformedContainer(index, container, "sector chain ends early")
            start = SECTOR_SIZE * sector
            header = self.data[start : start + SECTOR_HEADER]
            if len(header) < SECTOR_HEADER:
                raise MalformedContainer(index, container, "sector past the data file")
            held = (header[0] << 8) | header[1]
            held_part = (header[2] << 8) | header[3]
            following = (header[4] << 16) | (header[5] << 8) | header[6]
            held_index = header[7]
            if held != container or held_part != part or held_index != index:
                raise MalformedContainer(
                    index,
                    container,
                    f"sector {sector} holds index {held_index} container {held} "
                    f"part {held_part}",
                )
            take = min(SECTOR_PAYLOAD, size - len(out))
            out += self.data[start + SECTOR_HEADER : start + SECTOR_HEADER + take]
            part += 1
            sector = following
        return bytes(out)


def unpack(index: int, archive: int, packed: bytes) -> bytes:
    """Decompress one container, refusing anything its own header contradicts."""
    if len(packed) < CONTAINER_HEADER:
        raise ArchiveUnreadable(index, archive, "shorter than a container header")
    compression = packed[0]
    size = struct.unpack(">i", packed[1:5])[0]
    if size < 0 or size > MAX_CONTAINER:
        raise ArchiveUnreadable(index, archive, f"declares {size} packed bytes")
    if compression == NO_COMPRESSION:
        return packed[CONTAINER_HEADER : CONTAINER_HEADER + size]
    body_at = CONTAINER_HEADER + 4
    if len(packed) < body_at:
        raise ArchiveUnreadable(index, archive, "no room for an unpacked size")
    unpacked_size = struct.unpack(">i", packed[CONTAINER_HEADER:body_at])[0]
    if unpacked_size < 0 or unpacked_size > MAX_UNPACKED:
        raise ArchiveUnreadable(index, archive, f"declares {unpacked_size} bytes")
    body = packed[body_at : body_at + size]
    try:
        out = (
            bz2.decompress(BZIP2_MAGIC + body)
            if compression == BZIP2
            else gzip.decompress(body)
        )
    except (OSError, ValueError, EOFError) as error:
        raise ArchiveUnreadable(index, archive, str(error)) from error
    if len(out) < unpacked_size:
        raise ArchiveUnreadable(
            index, archive, f"unpacked {len(out)} of {unpacked_size} bytes"
        )
    return out[:unpacked_size]


def split_archive(
    index: int, archive: int, data: bytes, count: int
) -> tuple[bytes, ...]:
    """Cut an archive holding several files back into the files it was built from."""
    if count <= 1:
        return (data,)
    if not data:
        raise ArchiveUnreadable(index, archive, "empty archive holding several files")
    chunks = data[-1]
    table_at = len(data) - 1 - chunks * count * 4
    if table_at < 0:
        raise ArchiveUnreadable(index, archive, f"no room for {chunks} size tables")
    sizes = _sizes(data, table_at, chunks, count)
    parts: list[bytearray] = [bytearray() for _ in range(count)]
    read = table_at
    taken = 0
    for _ in range(chunks):
        length = 0
        for file_index in range(count):
            length += struct.unpack(">i", data[read : read + 4])[0]
            read += 4
            parts[file_index] += data[taken : taken + length]
            taken += length
    for file_index, size in enumerate(sizes):
        if len(parts[file_index]) != size:
            raise ArchiveUnreadable(
                index, archive, f"file {file_index} came out {len(parts[file_index])}"
            )
    return tuple(bytes(part) for part in parts)


def _sizes(data: bytes, table_at: int, chunks: int, count: int) -> list[int]:
    sizes = [0] * count
    read = table_at
    for _ in range(chunks):
        length = 0
        for file_index in range(count):
            length += struct.unpack(">i", data[read : read + 4])[0]
            read += 4
            sizes[file_index] += length
    return sizes


# test cases


def _sectors(index: int, container: int, payload: bytes) -> bytes:
    out = bytearray(SECTOR_SIZE)
    written = bytearray()
    part = 0
    sectors: list[bytes] = []
    while written != payload:
        take = payload[len(written) : len(written) + SECTOR_PAYLOAD]
        following = 0 if len(written) + len(take) >= len(payload) else 2 + part + 1
        header = bytes(
            [
                container >> 8,
                container & 0xFF,
                part >> 8,
                part & 0xFF,
                following >> 16,
                (following >> 8) & 0xFF,
                following & 0xFF,
                index,
            ]
        )
        sectors.append((header + take).ljust(SECTOR_SIZE, b"\x00"))
        written += take
        part += 1
    return bytes(out) * 2 + b"".join(sectors)


def _store(index: int, container: int, payload: bytes) -> CacheStore:
    entries = bytearray(ENTRY_SIZE * (container + 1))
    at = ENTRY_SIZE * container
    entries[at] = len(payload) >> 16
    entries[at + 1] = (len(payload) >> 8) & 0xFF
    entries[at + 2] = len(payload) & 0xFF
    entries[at + 5] = 2
    return CacheStore(
        directory=__import__("pathlib").Path("."),
        data=_sectors(index, container, payload),
        indexes={index: bytes(entries)},
    )


def test_a_container_is_read_back_out_of_its_sectors() -> None:
    payload = bytes(range(256)) * 5
    store = _store(19, 3, payload)
    assert store.container(19, 3) == payload


def test_a_container_the_index_does_not_list_is_absent() -> None:
    store = _store(19, 3, b"abc")
    assert store.container(19, 9) is None


def test_a_sector_holding_somebody_elses_data_is_refused() -> None:
    import pytest

    store = _store(19, 3, bytes(600))
    broken = bytearray(store.data)
    broken[SECTOR_SIZE * 2 + 7] = 5
    with pytest.raises(MalformedContainer):
        CacheStore(
            directory=store.directory, data=bytes(broken), indexes=store.indexes
        ).container(19, 3)


def test_an_uncompressed_container_unpacks_to_its_own_bytes() -> None:
    payload = b"plain bytes"
    packed = bytes([NO_COMPRESSION]) + struct.pack(">i", len(payload)) + payload
    assert unpack(19, 0, packed) == payload


def test_a_gzip_container_unpacks() -> None:
    payload = b"compressed bytes" * 4
    body = gzip.compress(payload)
    packed = (
        bytes([2])
        + struct.pack(">i", len(body))
        + struct.pack(">i", len(payload))
        + body
    )
    assert unpack(19, 0, packed) == payload


def test_a_bzip2_container_unpacks_without_the_magic_the_cache_strips() -> None:
    payload = b"compressed bytes" * 4
    body = bz2.compress(payload, compresslevel=1)[len(BZIP2_MAGIC) :]
    packed = (
        bytes([BZIP2])
        + struct.pack(">i", len(body))
        + struct.pack(">i", len(payload))
        + body
    )
    assert unpack(19, 0, packed) == payload


def test_a_container_that_does_not_decompress_names_the_archive() -> None:
    import pytest

    packed = bytes([2]) + struct.pack(">i", 4) + struct.pack(">i", 8) + b"junk"
    with pytest.raises(ArchiveUnreadable) as caught:
        unpack(5, 1234, packed)
    assert "archive 1234" in str(caught.value)


def test_one_file_archive_is_the_archive() -> None:
    assert split_archive(19, 0, b"only", 1) == (b"only",)


def test_an_archive_splits_back_into_its_files() -> None:
    files = (b"first file", b"second")
    table = struct.pack(">i", len(files[0])) + struct.pack(
        ">i", len(files[1]) - len(files[0])
    )
    data = b"".join(files) + table + bytes([1])
    assert split_archive(19, 0, data, 2) == files


def test_an_archive_too_short_for_its_size_table_is_refused() -> None:
    import pytest

    with pytest.raises(ArchiveUnreadable):
        split_archive(19, 0, bytes([9]), 4)


def test_an_empty_archive_holding_several_files_is_refused() -> None:
    import pytest

    with pytest.raises(ArchiveUnreadable):
        split_archive(19, 0, b"", 2)


def test_a_container_shorter_than_its_own_header_is_refused() -> None:
    import pytest

    with pytest.raises(ArchiveUnreadable):
        unpack(19, 0, b"\x02\x00")


def test_a_container_declaring_an_impossible_size_is_refused() -> None:
    import pytest

    for header in (
        bytes([0]) + struct.pack(">i", -1),
        bytes([2]) + struct.pack(">i", 4) + struct.pack(">i", -1),
        bytes([2]) + struct.pack(">i", 4) + struct.pack(">i", MAX_UNPACKED + 1),
    ):
        with pytest.raises(ArchiveUnreadable):
            unpack(19, 0, header + bytes(8))


def test_a_compressed_container_with_no_room_for_its_size_is_refused() -> None:
    import pytest

    with pytest.raises(ArchiveUnreadable):
        unpack(19, 0, bytes([2]) + struct.pack(">i", 4))


def test_a_container_that_unpacks_short_is_refused() -> None:
    import pytest

    body = gzip.compress(b"four")
    packed = bytes([2]) + struct.pack(">i", len(body)) + struct.pack(">i", 99) + body
    with pytest.raises(ArchiveUnreadable):
        unpack(19, 0, packed)


def test_an_index_entry_declaring_an_impossible_size_is_refused() -> None:
    import pytest

    store = _store(19, 0, b"abc")
    entries = bytearray(store.indexes[19])
    entries[0] = 0xFF
    entries[1] = 0xFF
    entries[2] = 0xFF
    with pytest.raises(MalformedContainer):
        CacheStore(
            directory=store.directory, data=store.data, indexes={19: bytes(entries)}
        ).container(19, 0)


def test_a_sector_pointing_past_the_data_file_is_absent() -> None:
    store = _store(19, 0, b"abc")
    entries = bytearray(store.indexes[19])
    entries[3] = 0xFF
    assert (
        CacheStore(
            directory=store.directory, data=store.data, indexes={19: bytes(entries)}
        ).container(19, 0)
        is None
    )


def test_a_sector_chain_that_ends_before_the_container_does_is_refused() -> None:
    import pytest

    store = _store(19, 3, bytes(600))
    broken = bytearray(store.data)
    broken[SECTOR_SIZE * 2 + 4 : SECTOR_SIZE * 2 + 7] = bytes(3)
    with pytest.raises(MalformedContainer):
        CacheStore(
            directory=store.directory, data=bytes(broken), indexes=store.indexes
        ).container(19, 3)
