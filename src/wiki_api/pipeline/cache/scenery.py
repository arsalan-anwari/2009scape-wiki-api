"""Decode index 16, opcode for opcode from the game's own SceneryDefinition."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import UnknownOpcode

KIND: Final = "scenery"
OPTION_SLOTS: Final = 5
END: Final = 0
HIDDEN_OPTION: Final = "Hidden"
NO_ID: Final = 65535


class SceneryDefinitionRecord(BaseModel):
    """One world object as the cache declares it."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str | None = None
    size_x: int = 1
    size_y: int = 1
    members_only: bool = False
    options: tuple[str | None, ...] = (None,) * OPTION_SLOTS

    @property
    def is_named(self) -> bool:
        """Whether the cache gives this object a name a reader would recognise."""
        return self.name is not None and self.name.lower() != "null"


def decode_scenery(scenery_id: int, data: bytes) -> SceneryDefinitionRecord:
    """Read one scenery definition, refusing an opcode the game does not declare."""
    reader = ByteReader(data, kind=KIND, identity=scenery_id)
    read: dict[str, object] = {"id": scenery_id}
    options: list[str | None] = [None] * OPTION_SLOTS
    while reader.remaining:
        at = reader.at
        opcode = reader.unsigned_byte()
        if opcode == END:
            break
        if opcode in (1, 5):
            _skip_models(reader, opcode)
        elif opcode == 2:
            read["name"] = reader.string()
        elif opcode == 14:
            read["size_x"] = reader.unsigned_byte()
        elif opcode == 15:
            read["size_y"] = reader.unsigned_byte()
        elif opcode in (17, 18, 21, 22, 23, 27, 62, 64, 73, 74, 89, 90, 94, 95):
            pass
        elif opcode == 19:
            reader.unsigned_byte()
        elif opcode == 24:
            reader.unsigned_short()
        elif opcode in (28, 29, 39):
            reader.signed_byte()
        elif 30 <= opcode < 35:
            options[opcode - 30] = _option(reader.string())
        elif opcode in (40, 41):
            reader.skip(reader.unsigned_byte() * 4)
        elif opcode == 42:
            reader.skip(reader.unsigned_byte())
        elif opcode == 60 or opcode in (65, 66, 67, 68, 70, 71, 72):
            reader.unsigned_short()
        elif opcode == 69 or opcode == 75:
            reader.unsigned_byte()
        elif opcode in (77, 92):
            _skip_children(reader, opcode)
        elif opcode == 78:
            reader.unsigned_short()
            reader.unsigned_byte()
        elif opcode == 79:
            _skip_sounds(reader)
        elif opcode == 81:
            reader.unsigned_byte()
        elif opcode in (82, 88, 96, 97):
            pass
        elif opcode == 91:
            read["members_only"] = True
        elif opcode == 93:
            reader.unsigned_short()
        elif opcode == 100:
            reader.unsigned_byte()
            reader.unsigned_short()
        elif opcode == 101:
            reader.unsigned_byte()
        elif opcode == 102:
            reader.unsigned_short()
        elif opcode == 249:
            _skip_scripts(reader)
        else:
            raise UnknownOpcode(KIND, scenery_id, opcode, at)
    read["options"] = tuple(options)
    return SceneryDefinitionRecord.model_validate(read)


def _option(read: str) -> str | None:
    return None if read == HIDDEN_OPTION else read


def _skip_models(reader: ByteReader, opcode: int) -> None:
    length = reader.unsigned_byte()
    reader.skip(length * (3 if opcode == 1 else 2))


def _skip_children(reader: ByteReader, opcode: int) -> None:
    reader.unsigned_short()
    reader.unsigned_short()
    if opcode == 92:
        reader.unsigned_short()
    children = reader.unsigned_byte()
    reader.skip((children + 1) * 2)


def _skip_sounds(reader: ByteReader) -> None:
    reader.unsigned_short()
    reader.unsigned_short()
    reader.unsigned_byte()
    reader.skip(reader.unsigned_byte() * 2)


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


def test_a_scenery_definition_decodes_its_name_size_and_options() -> None:
    record = decode_scenery(
        2728,
        bytes([2])
        + b"Furnace\x00"
        + bytes([14, 3])
        + bytes([15, 2])
        + bytes([30])
        + b"Smelt\x00"
        + bytes([91])
        + bytes([END]),
    )
    assert record.name == "Furnace"
    assert record.size_x == 3
    assert record.size_y == 2
    assert record.options[0] == "Smelt"
    assert record.members_only is True
    assert record.is_named is True


def test_a_hidden_option_is_left_out() -> None:
    record = decode_scenery(1, bytes([31]) + b"Hidden\x00" + bytes([END]))
    assert record.options[1] is None


def test_an_object_the_cache_calls_null_is_not_named() -> None:
    assert decode_scenery(1, bytes([2]) + b"null\x00" + bytes([END])).is_named is False


def test_the_model_and_child_fields_are_stepped_over() -> None:
    record = decode_scenery(
        1,
        bytes([1, 2])
        + bytes(6)
        + bytes([5, 1])
        + bytes(2)
        + bytes([77])
        + _short(3)
        + _short(4)
        + bytes([1])
        + bytes(4)
        + bytes([92])
        + _short(3)
        + _short(4)
        + _short(5)
        + bytes([0])
        + bytes(2)
        + bytes([79])
        + _short(1)
        + _short(2)
        + bytes([1, 2])
        + bytes(4)
        + bytes([2])
        + b"Anvil\x00"
        + bytes([END]),
    )
    assert record.name == "Anvil"


def test_a_definition_that_runs_out_of_bytes_stops_cleanly() -> None:
    record = decode_scenery(1, bytes([2]) + b"Rock\x00")
    assert record.name == "Rock"


def test_an_opcode_the_game_does_not_declare_stops_the_decode() -> None:
    import pytest

    with pytest.raises(UnknownOpcode):
        decode_scenery(1, bytes([200]))


def _every_scenery_opcode() -> bytes:
    out = bytearray()
    out += bytes([1, 1]) + _short(1) + bytes([10])
    out += bytes([5, 1]) + _short(2)
    out += bytes([2]) + b"Name\x00"
    out += bytes([14, 3])
    out += bytes([15, 4])
    silent = (17, 18, 21, 22, 23, 27, 62, 64, 73, 74, 82, 88, 89, 90, 94, 95, 96, 97)
    for opcode in silent:
        out += bytes([opcode])
    out += bytes([19, 1])
    out += bytes([24]) + _short(5)
    for opcode in (28, 29, 39):
        out += bytes([opcode]) + bytes([1])
    for opcode in range(30, 35):
        out += bytes([opcode]) + b"Option\x00"
    out += bytes([40, 1]) + _short(1) + _short(2)
    out += bytes([41, 1]) + _short(3) + _short(4)
    out += bytes([42, 2]) + bytes([1, 2])
    for opcode in (60, 65, 66, 67, 68, 70, 71, 72, 93, 102):
        out += bytes([opcode]) + _short(6)
    for opcode in (69, 75, 81, 101):
        out += bytes([opcode]) + bytes([1])
    out += bytes([77]) + _short(1) + _short(2) + bytes([1]) + _short(3) + _short(4)
    out += bytes([92]) + _short(1) + _short(2) + _short(3) + bytes([0]) + _short(4)
    out += bytes([78]) + _short(7) + bytes([1])
    out += bytes([79]) + _short(1) + _short(2) + bytes([1]) + bytes([1]) + _short(3)
    out += bytes([91])
    out += bytes([100]) + bytes([1]) + _short(2)
    out += bytes([249, 2]) + bytes([1]) + bytes([0, 0, 1]) + b"text\x00"
    out += bytes([0]) + bytes([0, 0, 2]) + bytes([0, 0, 0, 9])
    return bytes(out) + bytes([END])


def test_every_opcode_the_game_declares_is_read_without_losing_the_place() -> None:
    record = decode_scenery(2728, _every_scenery_opcode())
    assert record.name == "Name"
    assert record.size_x == 3
    assert record.size_y == 4
    assert record.members_only is True
    assert record.options == ("Option",) * OPTION_SLOTS
