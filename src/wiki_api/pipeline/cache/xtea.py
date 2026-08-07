"""Decrypt the map containers, with the keys the game reads from its own config."""

from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING, Any, Final

from wiki_api.pipeline.cache.errors import MalformedContainer

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

WORD_MASK: Final = 0xFFFFFFFF
DELTA: Final = 0x9E3779B9
ROUNDS: Final = 32
BLOCK: Final = 8
KEY_LENGTH: Final = 4
KEYS_FIELD: Final = "xteas"
REGION_FIELD: Final = "regionId"
KEY_FIELD: Final = "keys"
NO_KEY: Final = (0, 0, 0, 0)


def decipher(keys: tuple[int, ...], first: int, second: int) -> tuple[int, int]:
    """Turn one enciphered 64 bit block back into its two words."""
    total = (DELTA * ROUNDS) & WORD_MASK
    for _ in range(ROUNDS):
        second = (
            second
            - (
                (((first << 4) ^ (first >> 5)) + first)
                ^ (total + keys[(total >> 11) & 3])
            )
        ) & WORD_MASK
        total = (total - DELTA) & WORD_MASK
        first = (
            first
            - ((((second << 4) ^ (second >> 5)) + second) ^ (total + keys[total & 3]))
        ) & WORD_MASK
    return first, second


def decrypt(keys: tuple[int, ...], data: bytes, offset: int) -> bytes:
    """Decipher every whole block after the container header, leaving the rest alone."""
    if all(key == 0 for key in keys):
        return data
    out = bytearray(data)
    blocks = (len(data) - offset) // BLOCK
    for index in range(blocks):
        at = offset + index * BLOCK
        first, second = struct.unpack(">II", out[at : at + BLOCK])
        first, second = decipher(tuple(key & WORD_MASK for key in keys), first, second)
        out[at : at + BLOCK] = struct.pack(">II", first, second)
    return bytes(out)


def read_region_keys(path: Path) -> Mapping[int, tuple[int, ...]]:
    """Read the region decryption keys the game keeps beside its other config."""
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    rows = payload[KEYS_FIELD]
    keys: dict[int, tuple[int, ...]] = {}
    for row in rows:
        region = int(row[REGION_FIELD])
        parts = tuple(int(part) for part in str(row[KEY_FIELD]).split(","))
        if len(parts) != KEY_LENGTH:
            raise MalformedContainer(
                5, region, f"{len(parts)} key words, expected {KEY_LENGTH}"
            )
        keys[region] = parts
    return keys


# test cases


def _encipher(keys: tuple[int, ...], first: int, second: int) -> tuple[int, int]:
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


def test_a_block_survives_being_enciphered_and_deciphered() -> None:
    keys = (1, 2, 3, 4)
    enciphered = _encipher(keys, 0xDEADBEEF, 0x01020304)
    assert decipher(keys, *enciphered) == (0xDEADBEEF, 0x01020304)


def test_decrypting_leaves_the_header_and_any_tail_alone() -> None:
    header = b"\x02\x00\x00\x00\x08"
    body = bytes(range(8))
    tail = b"\x99"
    out = decrypt((5, 6, 7, 8), header + body + tail, offset=len(header))
    assert out[: len(header)] == header
    assert out[-1:] == tail
    assert out[len(header) : len(header) + BLOCK] != body


def test_a_container_with_no_key_is_handed_back_unchanged() -> None:
    data = bytes(range(32))
    assert decrypt(NO_KEY, data, offset=5) == data


def test_the_key_table_reads_back_by_region(tmp_path: Path) -> None:
    path = tmp_path / "xteas.json"
    path.write_text(
        json.dumps({KEYS_FIELD: [{REGION_FIELD: "6234", KEY_FIELD: "-1,2,-3,4"}]}),
        encoding="utf-8",
    )
    keys = read_region_keys(path)
    assert keys[6234] == (-1, 2, -3, 4)


def test_a_key_that_is_not_four_words_is_refused(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "xteas.json"
    path.write_text(
        json.dumps({KEYS_FIELD: [{REGION_FIELD: "1", KEY_FIELD: "1,2,3"}]}),
        encoding="utf-8",
    )
    with pytest.raises(MalformedContainer):
        read_region_keys(path)
