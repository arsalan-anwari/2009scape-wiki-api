"""Build a small game cache in a temporary place, for tests that read one."""

from __future__ import annotations

import gzip
import struct
from typing import TYPE_CHECKING

from wiki_api.pipeline.cache.containers import (
    DATA_FILE,
    ENTRY_SIZE,
    INDEX_FILE,
    REFERENCE_INDEX,
    SECTOR_PAYLOAD,
    SECTOR_SIZE,
)
from wiki_api.pipeline.cache.reference import HASH_MASK, NAMED_FLAG, name_hash
from wiki_api.pipeline.cache.xtea import decrypt

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

TABLE_REVISION = 214
RESERVED_SECTORS = 2


def container(payload: bytes) -> bytes:
    """Wrap bytes the way the cache stores a container, gzip compressed."""
    body = gzip.compress(payload, mtime=0)
    return (
        bytes([2])
        + struct.pack(">i", len(body))
        + struct.pack(">i", len(payload))
        + body
    )


def archive(files: Sequence[bytes]) -> bytes:
    """Join several file bodies into the one archive the cache stores them in."""
    if len(files) == 1:
        return files[0]
    table = b"".join(
        struct.pack(">i", len(body) - (len(files[position - 1]) if position else 0))
        for position, body in enumerate(files)
    )
    return b"".join(files) + table + bytes([1])


def reference_table(
    archives: Mapping[int, Sequence[int]], names: Mapping[int, str] | None = None
) -> bytes:
    """Write the reference table one index keeps, listing archives and their files."""
    named = names is not None
    out = bytearray()
    out.append(6)
    out += struct.pack(">i", TABLE_REVISION)
    out.append(NAMED_FLAG if named else 0)
    ordered = sorted(archives)
    out += struct.pack(">H", len(ordered))
    previous = 0
    for archive_id in ordered:
        out += struct.pack(">H", archive_id - previous)
        previous = archive_id
    if names is not None:
        for archive_id in ordered:
            out += struct.pack(">I", name_hash(names[archive_id]) & HASH_MASK)
    for _ in range(2):
        for _ in ordered:
            out += struct.pack(">i", 0)
    for archive_id in ordered:
        out += struct.pack(">H", len(archives[archive_id]))
    for archive_id in ordered:
        previous = 0
        for file_id in archives[archive_id]:
            out += struct.pack(">H", file_id - previous)
            previous = file_id
    return bytes(out)


def write_cache(
    directory: Path,
    containers: Mapping[int, Mapping[int, bytes]],
    references: Mapping[int, bytes],
) -> Path:
    """Write a cache directory holding these packed containers and reference tables."""
    directory.mkdir(parents=True, exist_ok=True)
    sectors = bytearray(SECTOR_SIZE * RESERVED_SECTORS)
    entries: dict[int, bytearray] = {}
    packed = {**containers, REFERENCE_INDEX: dict(references)}
    for index in sorted(packed):
        table = entries.setdefault(index, bytearray())
        for container_id in sorted(packed[index]):
            payload = packed[index][container_id]
            sector = len(sectors) // SECTOR_SIZE
            while len(table) < ENTRY_SIZE * container_id:
                table.append(0)
            table += bytes(
                [
                    len(payload) >> 16,
                    (len(payload) >> 8) & 0xFF,
                    len(payload) & 0xFF,
                    sector >> 16,
                    (sector >> 8) & 0xFF,
                    sector & 0xFF,
                ]
            )
            written = 0
            part = 0
            while written < len(payload):
                take = payload[written : written + SECTOR_PAYLOAD]
                written += len(take)
                following = 0 if written >= len(payload) else sector + part + 1
                header = bytes(
                    [
                        container_id >> 8,
                        container_id & 0xFF,
                        part >> 8,
                        part & 0xFF,
                        following >> 16,
                        (following >> 8) & 0xFF,
                        following & 0xFF,
                        index,
                    ]
                )
                sectors += (header + take).ljust(SECTOR_SIZE, b"\x00")
                part += 1
    (directory / DATA_FILE).write_bytes(bytes(sectors))
    for index, table in entries.items():
        (directory / INDEX_FILE.format(index=index)).write_bytes(bytes(table))
    return directory


def encrypted(payload: bytes, keys: tuple[int, ...]) -> bytes:
    """Wrap bytes as a container whose body is encrypted with these keys."""
    from wiki_api.pipeline.cache.containers import CONTAINER_HEADER
    from wiki_api.pipeline.cache.xtea import WORD_MASK

    plain = container(payload)
    out = bytearray(plain)
    for index in range((len(plain) - CONTAINER_HEADER) // 8):
        at = CONTAINER_HEADER + index * 8
        first, second = struct.unpack(">II", out[at : at + 8])
        first, second = _encipher(tuple(key & WORD_MASK for key in keys), first, second)
        out[at : at + 8] = struct.pack(">II", first, second)
    return bytes(out)


def _encipher(keys: tuple[int, ...], first: int, second: int) -> tuple[int, int]:
    from wiki_api.pipeline.cache.xtea import DELTA, ROUNDS, WORD_MASK

    total = 0
    for _ in range(ROUNDS):
        first = (
            first
            + ((((second << 4) ^ (second >> 5)) + second) ^ (total + keys[total & 3]))
        ) & WORD_MASK
        total = (total + DELTA) & WORD_MASK
        second = (
            second
            + (
                (((first << 4) ^ (first >> 5)) + first)
                ^ (total + keys[(total >> 11) & 3])
            )
        ) & WORD_MASK
    return first, second


def item_definition(name: str, value: int) -> bytes:
    """One item definition holding just a name and a value."""
    return (
        bytes([2])
        + name.encode("latin-1")
        + b"\x00"
        + bytes([12])
        + struct.pack(">i", value)
        + bytes([0])
    )


def quest_list() -> bytes:
    """The journal's own quest list, as the client's key-to-value maps hold it."""
    listed = {13: "Cook's Assistant", 14: "Dragon Slayer", 16: "Death Plateau"}
    body = bytes([1, ord("I"), 2, ord("s"), 5]) + struct.pack(">H", len(listed))
    for child, name in listed.items():
        body += (
            struct.pack(">I", (274 << 16) | child) + name.encode("latin-1") + b"\x00"
        )
    return body + bytes([0])


def map_label(name: str, rank: int, x: int, y: int) -> bytes:
    """One world map label, as index 23 holds it."""
    return name.encode("latin-1") + b"\x00" + struct.pack(">BHHi", rank, x, y, -1)


def built_cache(directory: Path) -> Path:
    """A cache holding one item, one scenery, one npc, one map, one label and the
    quest list.
    """
    from wiki_api.pipeline.cache.datamaps import DATAMAP_INDEX
    from wiki_api.pipeline.cache.reader import (
        ITEM_INDEX,
        MAP_INDEX,
        NPC_INDEX,
        SCENERY_INDEX,
        WORLDMAP_INDEX,
    )

    scenery = bytes([2]) + b"Furnace\x00" + bytes([30]) + b"Smelt\x00" + bytes([0])
    npc = bytes([2]) + b"Hans\x00" + bytes([95]) + struct.pack(">H", 4) + bytes([0])
    region = bytes([1, 2, 0b000100, 0, 0])
    labels = [map_label("Lumbridge", 9, 3222, 3218)]
    return write_cache(
        directory,
        {
            ITEM_INDEX: {
                17: container(archive([item_definition("Dragon scimitar", 100000)]))
            },
            SCENERY_INDEX: {0: container(archive([scenery]))},
            NPC_INDEX: {0: container(archive([npc]))},
            DATAMAP_INDEX: {1: container(archive([quest_list()]))},
            MAP_INDEX: {0: container(archive([region]))},
            WORLDMAP_INDEX: {2: container(archive(labels))},
        },
        {
            ITEM_INDEX: container(reference_table({17: [235]})),
            SCENERY_INDEX: container(reference_table({0: [0]})),
            NPC_INDEX: container(reference_table({0: [0]})),
            DATAMAP_INDEX: container(reference_table({1: [248]})),
            MAP_INDEX: container(reference_table({0: [0]}, names={0: "l50_50"})),
            WORLDMAP_INDEX: container(reference_table({2: [0]})),
        },
    )


# test cases


def test_a_built_cache_reads_back_through_the_reader(tmp_path: Path) -> None:
    from wiki_api.pipeline.cache.items import decode_item
    from wiki_api.pipeline.cache.reader import ITEM_INDEX, CacheReader

    reader = CacheReader.at(built_cache(tmp_path / "cache"), indexes=(ITEM_INDEX,))
    identity, body = reader.definitions(ITEM_INDEX)[0]
    assert identity == 17 * 256 + 235
    assert decode_item(identity, body).value == 100000


def test_an_archive_holding_several_files_splits_back(tmp_path: Path) -> None:
    from wiki_api.pipeline.cache.containers import split_archive

    files = [b"first", b"second file"]
    assert split_archive(19, 0, archive(files), len(files)) == tuple(files)


def test_a_named_archive_is_found_by_the_name_the_game_asks_for(tmp_path: Path) -> None:
    from wiki_api.pipeline.cache.reader import MAP_INDEX, CacheReader

    reader = CacheReader.at(built_cache(tmp_path / "cache"), indexes=(MAP_INDEX,))
    assert reader.table(MAP_INDEX).archive_named("l50_50") == 0


def test_an_encrypted_container_needs_its_keys(tmp_path: Path) -> None:
    keys = (1, 2, 3, 4)
    payload = b"landscape bytes" * 4
    packed = encrypted(payload, keys)
    from wiki_api.pipeline.cache.containers import CONTAINER_HEADER, unpack

    assert unpack(5, 0, decrypt(keys, packed, CONTAINER_HEADER)) == payload
