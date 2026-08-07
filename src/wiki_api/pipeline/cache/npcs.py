"""Decode index 18, opcode for opcode from the game's own NPCDefinition."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import UnknownOpcode

KIND: Final = "npc"
OPTION_SLOTS: Final = 5
END: Final = 0


class NpcDefinitionRecord(BaseModel):
    """One npc as the cache declares it."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str | None = None
    size: int = 1
    combat_level: int | None = None
    visible_on_map: bool = True
    options: tuple[str | None, ...] = (None,) * OPTION_SLOTS

    @property
    def fights(self) -> bool:
        """Whether the cache gives this npc a level, which only fighting ones carry."""
        return self.combat_level is not None and self.combat_level > 0


def decode_npc(npc_id: int, data: bytes) -> NpcDefinitionRecord:
    """Read one npc definition, refusing an opcode the game does not declare."""
    reader = ByteReader(data, kind=KIND, identity=npc_id)
    read: dict[str, object] = {"id": npc_id}
    options: list[str | None] = [None] * OPTION_SLOTS
    while True:
        at = reader.at
        opcode = reader.unsigned_byte()
        if opcode == END:
            break
        if opcode == 1:
            reader.skip(reader.unsigned_byte() * 2)
        elif opcode == 2:
            read["name"] = reader.string()
        elif opcode == 12:
            read["size"] = reader.unsigned_byte()
        elif opcode in (13, 14, 15, 16):
            reader.unsigned_short()
        elif opcode == 17:
            reader.skip(8)
        elif 30 <= opcode < 35:
            options[opcode - 30] = reader.string()
        elif opcode in (40, 41):
            reader.skip(reader.unsigned_byte() * 4)
        elif opcode == 42:
            reader.skip(reader.unsigned_byte())
        elif opcode == 60:
            reader.skip(reader.unsigned_byte() * 2)
        elif opcode == 93:
            read["visible_on_map"] = False
        elif opcode == 95:
            read["combat_level"] = reader.unsigned_short()
        elif opcode in (97, 98, 102, 103):
            reader.unsigned_short()
        elif opcode == 99:
            pass
        elif opcode in (100, 101):
            reader.signed_byte()
        elif opcode in (106, 118):
            _skip_children(reader, opcode)
        elif opcode in (107, 109, 111):
            pass
        elif opcode == 113:
            reader.skip(4)
        elif opcode in (114, 115):
            reader.skip(2)
        elif opcode == 119:
            reader.signed_byte()
        elif opcode == 121:
            reader.skip(reader.unsigned_byte() * 4)
        elif opcode in (122, 123):
            reader.unsigned_short()
        elif opcode == 125:
            reader.signed_byte()
        elif opcode == 126:
            reader.unsigned_short()
            reader.unsigned_short()
        elif opcode == 127:
            reader.unsigned_short()
        elif opcode == 128:
            reader.signed_byte()
        elif opcode == 134:
            reader.skip(9)
        elif opcode in (135, 136):
            reader.signed_byte()
            reader.unsigned_short()
        elif opcode == 137:
            reader.unsigned_short()
        elif opcode == 249:
            _skip_scripts(reader)
        else:
            raise UnknownOpcode(KIND, npc_id, opcode, at)
    read["options"] = tuple(options)
    return NpcDefinitionRecord.model_validate(read)


def _skip_children(reader: ByteReader, opcode: int) -> None:
    reader.unsigned_short()
    reader.unsigned_short()
    if opcode == 118:
        reader.unsigned_short()
    children = reader.unsigned_byte()
    reader.skip((children + 1) * 2)


def _skip_scripts(reader: ByteReader) -> None:
    for _ in range(reader.unsigned_byte()):
        is_string = reader.unsigned_byte() == 1
        reader.medium()
        if is_string:
            reader.string()
        else:
            reader.integer()


# test cases


def _short(value: int) -> bytes:
    return bytes([value >> 8, value & 0xFF])


def test_an_npc_decodes_its_name_level_and_options() -> None:
    record = decode_npc(
        50,
        bytes([2])
        + b"King Black Dragon\x00"
        + bytes([12, 5])
        + bytes([31])
        + b"Attack\x00"
        + bytes([95])
        + _short(276)
        + bytes([END]),
    )
    assert record.name == "King Black Dragon"
    assert record.size == 5
    assert record.combat_level == 276
    assert record.options[1] == "Attack"
    assert record.fights is True


def test_an_npc_with_no_level_does_not_fight() -> None:
    record = decode_npc(0, bytes([2]) + b"Hans\x00" + bytes([END]))
    assert record.combat_level is None
    assert record.fights is False


def test_an_npc_kept_off_the_map_says_so() -> None:
    assert decode_npc(1, bytes([93]) + bytes([END])).visible_on_map is False


def test_the_wide_fields_are_stepped_over() -> None:
    record = decode_npc(
        1,
        bytes([1, 2])
        + bytes(4)
        + bytes([17])
        + bytes(8)
        + bytes([106])
        + _short(1)
        + _short(2)
        + bytes([1])
        + bytes(4)
        + bytes([118])
        + _short(1)
        + _short(2)
        + _short(3)
        + bytes([0])
        + bytes(2)
        + bytes([134])
        + bytes(9)
        + bytes([2])
        + b"Man\x00"
        + bytes([END]),
    )
    assert record.name == "Man"


def test_an_opcode_the_game_does_not_declare_stops_the_decode() -> None:
    import pytest

    with pytest.raises(UnknownOpcode):
        decode_npc(1, bytes([200]))


def _every_npc_opcode() -> bytes:
    out = bytearray()
    out += bytes([1, 1]) + _short(1)
    out += bytes([2]) + b"Name\x00"
    out += bytes([12, 5])
    for opcode in (13, 14, 15, 16, 97, 98, 102, 103, 122, 123, 127, 137):
        out += bytes([opcode]) + _short(2)
    out += bytes([17]) + _short(1) + _short(2) + _short(3) + _short(4)
    for opcode in range(30, 35):
        out += bytes([opcode]) + b"Option\x00"
    out += bytes([40, 1]) + _short(1) + _short(2)
    out += bytes([41, 1]) + _short(3) + _short(4)
    out += bytes([42, 2]) + bytes([1, 2])
    out += bytes([60, 1]) + _short(5)
    out += bytes([93])
    out += bytes([95]) + _short(276)
    out += bytes([99])
    for opcode in (100, 101, 119, 125, 128):
        out += bytes([opcode]) + bytes([1])
    out += bytes([106]) + _short(1) + _short(2) + bytes([1]) + _short(3) + _short(4)
    out += bytes([118]) + _short(1) + _short(2) + _short(3) + bytes([0]) + _short(4)
    for opcode in (107, 109, 111):
        out += bytes([opcode])
    out += bytes([113]) + _short(1) + _short(2)
    out += bytes([114]) + bytes([1, 2])
    out += bytes([115]) + bytes([1, 2])
    out += bytes([121, 1]) + bytes([1, 2, 3, 4])
    out += bytes([126]) + _short(1) + _short(2)
    out += bytes([134]) + _short(1) + _short(2) + _short(3) + _short(4) + bytes([1])
    for opcode in (135, 136):
        out += bytes([opcode]) + bytes([1]) + _short(2)
    out += bytes([249, 2]) + bytes([1]) + bytes([0, 0, 1]) + b"text\x00"
    out += bytes([0]) + bytes([0, 0, 2]) + bytes([0, 0, 0, 9])
    return bytes(out) + bytes([END])


def test_every_opcode_the_game_declares_is_read_without_losing_the_place() -> None:
    record = decode_npc(50, _every_npc_opcode())
    assert record.name == "Name"
    assert record.size == 5
    assert record.combat_level == 276
    assert record.visible_on_map is False
    assert record.options == ("Option",) * OPTION_SLOTS
