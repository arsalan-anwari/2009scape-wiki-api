"""Decode the client's own key-to-value maps, opcode for opcode from DataMap.java."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import UnknownOpcode

KIND: Final = "datamap"
DATAMAP_INDEX: Final = 17
END: Final = 0
KEY_TYPE: Final = 1
VALUE_TYPE: Final = 2
DEFAULT_STRING: Final = 3
DEFAULT_INT: Final = 4
STRING_ENTRIES: Final = 5
INT_ENTRIES: Final = 6


class DataMap(BaseModel):
    """One map the client reads by id, with its keys left exactly as written."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    key_type: str = ""
    value_type: str = ""
    strings: dict[int, str] = Field(default_factory=dict)
    numbers: dict[int, int] = Field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.strings) + len(self.numbers)


def decode_datamap(identity: int, body: bytes) -> DataMap:
    """Read one map, refusing an opcode the game's own reader does not declare."""
    reader = ByteReader(body, KIND, identity)
    key_type = value_type = ""
    strings: dict[int, str] = {}
    numbers: dict[int, int] = {}
    while True:
        opcode = reader.unsigned_byte()
        if opcode == END:
            break
        if opcode == KEY_TYPE:
            key_type = chr(reader.unsigned_byte())
        elif opcode == VALUE_TYPE:
            value_type = chr(reader.unsigned_byte())
        elif opcode == DEFAULT_STRING:
            reader.string()
        elif opcode == DEFAULT_INT:
            reader.integer()
        elif opcode in (STRING_ENTRIES, INT_ENTRIES):
            for _ in range(reader.unsigned_short()):
                key = reader.integer()
                if opcode == STRING_ENTRIES:
                    strings[key] = reader.string()
                else:
                    numbers[key] = reader.integer()
        else:
            raise UnknownOpcode(KIND, identity, opcode, reader.at)
    return DataMap(
        id=identity,
        key_type=key_type,
        value_type=value_type,
        strings=strings,
        numbers=numbers,
    )


# test cases


def _written(*chunks: bytes) -> bytes:
    return b"".join(chunks) + bytes([END])


def _string_entries(entries: dict[int, str]) -> bytes:
    body = bytes([STRING_ENTRIES]) + len(entries).to_bytes(2, "big")
    for key, value in entries.items():
        body += key.to_bytes(4, "big") + value.encode("latin-1") + b"\x00"
    return body


def test_a_map_of_names_reads_back_key_for_key() -> None:
    body = _written(
        bytes([KEY_TYPE, ord("i"), VALUE_TYPE, ord("s")]),
        _string_entries({13: "Cook's Assistant", 14: "Demon Slayer"}),
    )
    read = decode_datamap(504, body)
    assert read.id == 504
    assert read.key_type == "i"
    assert read.value_type == "s"
    assert read.strings == {13: "Cook's Assistant", 14: "Demon Slayer"}
    assert read.count == 2


def test_a_map_of_numbers_reads_back_as_numbers() -> None:
    body = _written(
        bytes([INT_ENTRIES])
        + (1).to_bytes(2, "big")
        + (7).to_bytes(4, "big")
        + (900).to_bytes(4, "big")
    )
    assert decode_datamap(1351, body).numbers == {7: 900}


def test_a_default_is_read_past_rather_than_kept() -> None:
    body = _written(bytes([DEFAULT_INT]) + (5).to_bytes(4, "big"))
    assert decode_datamap(1, body).count == 0


def test_an_opcode_the_game_does_not_declare_is_refused() -> None:
    import pytest

    with pytest.raises(UnknownOpcode) as caught:
        decode_datamap(9, bytes([99, 0]))
    assert caught.value.opcode == 99
