"""Read the primitives the cache's own buffer helpers write."""

from __future__ import annotations

from typing import Final

from wiki_api.pipeline.cache.errors import TruncatedDefinition

STRING_ENCODING: Final = "latin-1"
SMART_LIMIT: Final = 127
SMART_BIAS: Final = 32768
BIG_SMART_STEP: Final = 32767
SIGN_BIT: Final = 1 << 31
WORD: Final = 1 << 32


class ByteReader:
    """A cursor over one definition's bytes, refusing to read past the end."""

    def __init__(
        self, data: bytes, kind: str = "definition", identity: int = 0
    ) -> None:
        self._data = data
        self._at = 0
        self._kind = kind
        self._identity = identity

    @property
    def at(self) -> int:
        return self._at

    @property
    def remaining(self) -> int:
        return len(self._data) - self._at

    def _take(self, count: int) -> bytes:
        if self.remaining < count:
            raise TruncatedDefinition(self._kind, self._identity, count, self.remaining)
        taken = self._data[self._at : self._at + count]
        self._at += count
        return taken

    def skip(self, count: int) -> None:
        """Step over bytes whose meaning this decoder does not keep."""
        self._take(count)

    def unsigned_byte(self) -> int:
        return self._take(1)[0]

    def signed_byte(self) -> int:
        value = self._take(1)[0]
        return value - 256 if value > 127 else value

    def unsigned_short(self) -> int:
        taken = self._take(2)
        return (taken[0] << 8) | taken[1]

    def signed_short(self) -> int:
        value = self.unsigned_short()
        return value - 65536 if value > 32767 else value

    def medium(self) -> int:
        taken = self._take(3)
        return (taken[0] << 16) | (taken[1] << 8) | taken[2]

    def integer(self) -> int:
        taken = self._take(4)
        value = (taken[0] << 24) | (taken[1] << 16) | (taken[2] << 8) | taken[3]
        return value - WORD if value & SIGN_BIT else value

    def string(self) -> str:
        start = self._at
        while True:
            if self.remaining == 0:
                raise TruncatedDefinition(self._kind, self._identity, 1, 0)
            if self._data[self._at] == 0:
                break
            self._at += 1
        text = self._data[start : self._at].decode(STRING_ENCODING)
        self._at += 1
        return text

    def smart(self) -> int:
        peek = self._take(1)[0]
        if peek <= SMART_LIMIT:
            return peek
        return ((peek << 8) | self._take(1)[0]) - SMART_BIAS

    def big_smart(self) -> int:
        value = 0
        current = self.smart()
        while current == BIG_SMART_STEP:
            current = self.smart()
            value += BIG_SMART_STEP
        return value + current


# test cases


def test_the_readers_cover_the_widths_the_definitions_use() -> None:
    reader = ByteReader(bytes([0xFF, 0x01, 0x02, 0x00, 0x00, 0x00, 0x0A]))
    assert reader.unsigned_byte() == 255
    assert reader.unsigned_short() == 258
    assert reader.integer() == 10
    assert reader.remaining == 0


def test_a_signed_read_comes_back_negative() -> None:
    assert ByteReader(bytes([0xFF])).signed_byte() == -1
    assert ByteReader(bytes([0xFF, 0xFF])).signed_short() == -1
    assert ByteReader(bytes([0xFF, 0xFF, 0xFF, 0xFF])).integer() == -1


def test_a_medium_is_three_bytes_big_endian() -> None:
    assert ByteReader(bytes([0x01, 0x00, 0x00])).medium() == 65536


def test_a_string_ends_at_the_first_zero() -> None:
    reader = ByteReader(b"Dragon scimitar\x00rest")
    assert reader.string() == "Dragon scimitar"
    assert reader.remaining == 4


def test_a_smart_reads_one_byte_below_the_limit_and_two_above() -> None:
    assert ByteReader(bytes([0x7F])).smart() == 127
    assert ByteReader(bytes([0x80, 0x80])).smart() == 128


def test_a_big_smart_adds_up_the_steps() -> None:
    step = bytes([0xFF, 0xFF])
    assert ByteReader(step + bytes([0x01])).big_smart() == 32768


def test_reading_past_the_end_names_the_definition() -> None:
    import pytest

    reader = ByteReader(bytes([0x01]), kind="item", identity=4587)
    with pytest.raises(TruncatedDefinition) as caught:
        reader.integer()
    assert "item 4587" in str(caught.value)


def test_an_unterminated_string_is_refused() -> None:
    import pytest

    with pytest.raises(TruncatedDefinition):
        ByteReader(b"no end").string()


def test_the_cursor_says_where_it_is() -> None:
    reader = ByteReader(bytes(4))
    reader.skip(3)
    assert reader.at == 3
    assert reader.remaining == 1
