"""Read one index's reference table: which archives it holds, and which files."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import MalformedContainer

NAMED_FLAG: Final = 0x1
WHIRLPOOL_FLAG: Final = 0x2
WHIRLPOOL_SIZE: Final = 64
VERSIONED_PROTOCOL: Final = 6
PROTOCOLS: Final = (5, 6)
HASH_MASK: Final = 0xFFFFFFFF
HASH_SIGN: Final = 1 << 31
HASH_WORD: Final = 1 << 32


def name_hash(name: str) -> int:
    """Hash an archive name the way the game looks one up."""
    value = 0
    for char in name.lower():
        value = (ord(char) + ((value << 5) - value)) & HASH_MASK
    return value - HASH_WORD if value & HASH_SIGN else value


class ReferenceTable(BaseModel):
    """What one index says about itself."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    protocol: int = Field(ge=0)
    revision: int = Field(ge=0)
    archives: tuple[int, ...] = ()
    files: Mapping[int, tuple[int, ...]] = Field(default_factory=dict)
    names: Mapping[int, int] = Field(default_factory=dict)

    @property
    def file_count(self) -> int:
        return sum(len(ids) for ids in self.files.values())

    def archive_named(self, name: str) -> int | None:
        """The archive carrying a name, for the indexes that name their archives."""
        wanted = name_hash(name)
        for archive, hashed in self.names.items():
            if hashed == wanted:
                return archive
        return None


def read_reference(index: int, data: bytes) -> ReferenceTable:
    """Parse the reference table the cache keeps for one index."""
    reader = ByteReader(data, kind="reference table", identity=index)
    protocol = reader.unsigned_byte()
    if protocol not in PROTOCOLS:
        raise MalformedContainer(255, index, f"reference protocol {protocol}")
    revision = reader.integer() if protocol >= VERSIONED_PROTOCOL else 0
    flags = reader.unsigned_byte()
    named = bool(flags & NAMED_FLAG)
    whirlpool = bool(flags & WHIRLPOOL_FLAG)
    archives = _deltas(reader, reader.unsigned_short())
    names = {archive: reader.integer() for archive in archives} if named else {}
    if whirlpool:
        reader.skip(WHIRLPOOL_SIZE * len(archives))
    for _ in archives:
        reader.integer()
    for _ in archives:
        reader.integer()
    counts = {archive: reader.unsigned_short() for archive in archives}
    files = {archive: _deltas(reader, counts[archive]) for archive in archives}
    return ReferenceTable(
        index=index,
        protocol=protocol,
        revision=max(revision, 0),
        archives=archives,
        files=files,
        names=names,
    )


def _deltas(reader: ByteReader, count: int) -> tuple[int, ...]:
    read: list[int] = []
    running = 0
    for position in range(count):
        running = reader.unsigned_short() + (0 if position == 0 else running)
        read.append(running)
    return tuple(read)


# test cases


def _table(*, named: bool = False) -> bytes:
    import struct

    out = bytearray()
    out.append(6)
    out += struct.pack(">i", 214)
    out.append(NAMED_FLAG if named else 0)
    out += struct.pack(">H", 2)
    out += struct.pack(">H", 0)
    out += struct.pack(">H", 3)
    if named:
        out += struct.pack(">I", name_hash("l50_50") & HASH_MASK)
        out += struct.pack(">I", name_hash("m50_50") & HASH_MASK)
    for _ in range(4):
        out += struct.pack(">i", 0)
    out += struct.pack(">H", 2)
    out += struct.pack(">H", 1)
    out += struct.pack(">H", 0)
    out += struct.pack(">H", 1)
    out += struct.pack(">H", 0)
    return bytes(out)


def test_a_reference_table_lists_its_archives_and_their_files() -> None:
    table = read_reference(19, _table())
    assert table.revision == 214
    assert table.archives == (0, 3)
    assert table.files == {0: (0, 1), 3: (0,)}
    assert table.file_count == 3


def test_an_archive_can_be_found_by_the_name_the_game_asks_for() -> None:
    table = read_reference(5, _table(named=True))
    assert table.archive_named("l50_50") == 0
    assert table.archive_named("m50_50") == 3
    assert table.archive_named("l99_99") is None


def test_an_unnamed_index_finds_nothing_by_name() -> None:
    assert read_reference(19, _table()).archive_named("l50_50") is None


def test_the_name_hash_matches_the_games_own() -> None:
    assert name_hash("m50_50") == name_hash("M50_50")
    assert name_hash("l0_0") != name_hash("l0_1")


def test_a_protocol_this_decoder_does_not_know_is_refused() -> None:
    import pytest

    with pytest.raises(MalformedContainer):
        read_reference(19, bytes([4]))
