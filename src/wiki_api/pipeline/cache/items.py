"""Decode index 19, opcode for opcode from the game's own ItemDefinition."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import UnknownOpcode

KIND: Final = "item"
OPTION_SLOTS: Final = 5
STACK_SLOTS: Final = 10
END: Final = 0
NO_ID: Final = 65535


class ItemDefinitionRecord(BaseModel):
    """One item as the cache declares it."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    name: str | None = None
    examine: str | None = None
    value: int | None = None
    stackable: bool = False
    members_only: bool = False
    unnoted: bool = False
    note_id: int | None = None
    note_template_id: int | None = None
    lend_id: int | None = None
    lend_template_id: int | None = None
    team_id: int | None = None
    options: tuple[str | None, ...] = (None,) * OPTION_SLOTS

    @property
    def is_noted(self) -> bool:
        """Whether this item is the note of another one rather than a real item."""
        return self.note_template_id is not None and self.note_id is not None

    @property
    def is_lent(self) -> bool:
        """Whether this item is the lent copy of another one."""
        return self.lend_template_id is not None and self.lend_id is not None


def decode_item(item_id: int, data: bytes) -> ItemDefinitionRecord:
    """Read one item definition, refusing an opcode the game does not declare."""
    reader = ByteReader(data, kind=KIND, identity=item_id)
    read: dict[str, object] = {"id": item_id}
    options: list[str | None] = [None] * OPTION_SLOTS
    while True:
        at = reader.at
        opcode = reader.unsigned_byte()
        if opcode == END:
            break
        if opcode == 1:
            reader.unsigned_short()
        elif opcode == 2:
            read["name"] = reader.string()
        elif opcode == 3:
            read["examine"] = reader.string()
        elif opcode in (4, 5, 6, 7, 8):
            reader.unsigned_short()
        elif opcode == 10:
            pass
        elif opcode == 11:
            read["stackable"] = True
        elif opcode == 12:
            read["value"] = reader.integer()
        elif opcode == 16:
            read["members_only"] = True
        elif opcode in (23, 24, 25, 26):
            reader.unsigned_short()
        elif 30 <= opcode < 35:
            reader.string()
        elif 35 <= opcode < 40:
            options[opcode - 35] = reader.string()
        elif opcode in (40, 41):
            reader.skip(reader.unsigned_byte() * 4)
        elif opcode == 42:
            reader.skip(reader.unsigned_byte())
        elif opcode == 65:
            read["unnoted"] = True
        elif opcode in (78, 79, 90, 91, 92, 93, 95):
            reader.unsigned_short()
        elif opcode == 96:
            reader.signed_byte()
        elif opcode == 97:
            read["note_id"] = reader.unsigned_short()
        elif opcode == 98:
            read["note_template_id"] = reader.unsigned_short()
        elif 100 <= opcode < 100 + STACK_SLOTS:
            reader.unsigned_short()
            reader.unsigned_short()
        elif opcode in (110, 111, 112):
            reader.unsigned_short()
        elif opcode in (113, 114):
            reader.signed_byte()
        elif opcode == 115:
            read["team_id"] = reader.signed_byte()
        elif opcode == 121:
            read["lend_id"] = reader.unsigned_short()
        elif opcode == 122:
            read["lend_template_id"] = reader.unsigned_short()
        elif opcode in (125, 126):
            reader.skip(3)
        elif opcode in (127, 128, 129, 130):
            reader.signed_byte()
            reader.unsigned_short()
        elif opcode == 249:
            _skip_scripts(reader)
        else:
            raise UnknownOpcode(KIND, item_id, opcode, at)
    read["options"] = tuple(options)
    return ItemDefinitionRecord.model_validate(read)


def _skip_scripts(reader: ByteReader) -> None:
    for _ in range(reader.unsigned_byte()):
        is_string = reader.unsigned_byte() == 1
        reader.medium()
        if is_string:
            reader.string()
        else:
            reader.integer()


# test cases


def _definition(*parts: bytes) -> bytes:
    return b"".join(parts) + bytes([END])


def _short(value: int) -> bytes:
    return bytes([value >> 8, value & 0xFF])


def _int(value: int) -> bytes:
    return bytes(
        [value >> 24 & 0xFF, value >> 16 & 0xFF, value >> 8 & 0xFF, value & 0xFF]
    )


def test_an_item_decodes_its_name_value_and_options() -> None:
    record = decode_item(
        4587,
        _definition(
            bytes([2]) + b"Dragon scimitar\x00",
            bytes([12]) + _int(100000),
            bytes([16]),
            bytes([36]) + b"Wield\x00",
            bytes([65]),
            bytes([97]) + _short(4588),
            bytes([121]) + _short(13477),
        ),
    )
    assert record.name == "Dragon scimitar"
    assert record.value == 100000
    assert record.members_only is True
    assert record.options[1] == "Wield"
    assert record.unnoted is True
    assert record.note_id == 4588
    assert record.lend_id == 13477


def test_a_note_names_the_item_it_copies() -> None:
    record = decode_item(
        4588, _definition(bytes([97]) + _short(4587), bytes([98]) + _short(799))
    )
    assert record.is_noted is True
    assert record.is_lent is False
    assert record.note_id == 4587


def test_an_item_holding_a_note_id_but_no_template_is_not_a_note() -> None:
    record = decode_item(4587, _definition(bytes([97]) + _short(4588)))
    assert record.is_noted is False


def test_a_lent_copy_names_the_item_it_copies() -> None:
    record = decode_item(
        13477, _definition(bytes([121]) + _short(4587), bytes([122]) + _short(13476))
    )
    assert record.is_lent is True


def test_the_wide_fields_are_stepped_over_without_losing_the_place() -> None:
    record = decode_item(
        1,
        _definition(
            bytes([40, 2]) + _short(1) + _short(2) + _short(3) + _short(4),
            bytes([42, 3]) + bytes([1, 2, 3]),
            bytes([125]) + bytes([1, 2, 3]),
            bytes([127]) + bytes([1]) + _short(2),
            bytes([249, 2])
            + bytes([1])
            + bytes([0, 0, 1])
            + b"text\x00"
            + bytes([0])
            + bytes([0, 0, 2])
            + _int(9),
            bytes([2]) + b"Coins\x00",
        ),
    )
    assert record.name == "Coins"


def test_an_empty_definition_is_a_bare_record() -> None:
    record = decode_item(9, bytes([END]))
    assert record.name is None
    assert record.value is None
    assert record.options == (None,) * OPTION_SLOTS


def test_an_opcode_the_game_does_not_declare_stops_the_decode() -> None:
    import pytest

    with pytest.raises(UnknownOpcode) as caught:
        decode_item(4587, bytes([2]) + b"X\x00" + bytes([200]))
    assert caught.value.opcode == 200
    assert caught.value.offset == 3


def _every_item_opcode() -> bytes:
    out = bytearray()
    for opcode in (1, 4, 5, 6, 7, 8, 23, 24, 25, 26, 78, 79, 90, 91, 92, 93, 95):
        out += bytes([opcode]) + _short(1)
    out += bytes([2]) + b"Name\x00"
    out += bytes([3]) + b"Examine\x00"
    out += bytes([10])
    out += bytes([11])
    out += bytes([12]) + _int(7)
    out += bytes([16])
    for opcode in range(30, 35):
        out += bytes([opcode]) + b"Ground\x00"
    for opcode in range(35, 40):
        out += bytes([opcode]) + b"Option\x00"
    out += bytes([40, 1]) + _short(1) + _short(2)
    out += bytes([41, 1]) + _short(3) + _short(4)
    out += bytes([42, 2]) + bytes([1, 2])
    out += bytes([65])
    out += bytes([96]) + bytes([1])
    out += bytes([97]) + _short(11)
    out += bytes([98]) + _short(12)
    for opcode in range(100, 110):
        out += bytes([opcode]) + _short(1) + _short(2)
    for opcode in (110, 111, 112):
        out += bytes([opcode]) + _short(1)
    for opcode in (113, 114):
        out += bytes([opcode]) + bytes([1])
    out += bytes([115]) + bytes([2])
    out += bytes([121]) + _short(13)
    out += bytes([122]) + _short(14)
    for opcode in (125, 126):
        out += bytes([opcode]) + bytes([1, 2, 3])
    for opcode in (127, 128, 129, 130):
        out += bytes([opcode]) + bytes([1]) + _short(2)
    out += bytes([249, 2]) + bytes([1]) + bytes([0, 0, 1]) + b"text\x00"
    out += bytes([0]) + bytes([0, 0, 2]) + _int(9)
    return bytes(out) + bytes([END])


def test_every_opcode_the_game_declares_is_read_without_losing_the_place() -> None:
    record = decode_item(4587, _every_item_opcode())
    assert record.name == "Name"
    assert record.examine == "Examine"
    assert record.value == 7
    assert record.stackable is True
    assert record.members_only is True
    assert record.unnoted is True
    assert record.note_id == 11
    assert record.note_template_id == 12
    assert record.lend_id == 13
    assert record.lend_template_id == 14
    assert record.team_id == 2
    assert record.options == ("Option",) * OPTION_SLOTS
