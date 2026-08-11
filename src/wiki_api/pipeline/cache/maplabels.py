"""Decode the world map labels the client draws over the map, in index 23.

Archive 2 of that index is the gazetteer the game ships: a name the game wrote, a rank
saying how large to draw it, and the tile the name sits over.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader
from wiki_api.pipeline.cache.errors import UnknownOpcode

KIND: Final = "map label"
LINE_BREAK: Final = "<br>"
NO_FOLLOWER: Final = -1
SMALLEST_RANK: Final = 8
LARGEST_RANK: Final = 10


class MapLabel(BaseModel):
    """One name the world map draws, and the tile it is drawn over."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    rank: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)

    @property
    def is_wide(self) -> bool:
        """Whether the map draws this one as a region rather than a landmark."""
        return self.rank > SMALLEST_RANK


def decode_map_label(identity: int, data: bytes) -> MapLabel:
    """Read one label, refusing anything the shape does not account for."""
    reader = ByteReader(data, kind=KIND, identity=identity)
    name = reader.string().replace(LINE_BREAK, " ").strip()
    rank = reader.unsigned_byte()
    x = reader.unsigned_short()
    y = reader.unsigned_short()
    follower = reader.integer()
    if follower != NO_FOLLOWER:
        raise UnknownOpcode(KIND, identity, follower, reader.at)
    if not SMALLEST_RANK <= rank <= LARGEST_RANK:
        raise UnknownOpcode(KIND, identity, rank, reader.at)
    return MapLabel(name=name, rank=rank, x=x, y=y)


# test cases


def _label(name: str, rank: int, x: int, y: int, follower: int = NO_FOLLOWER) -> bytes:
    import struct

    return name.encode("latin-1") + b"\0" + struct.pack(">BHHi", rank, x, y, follower)


def test_a_label_reads_back_as_a_name_over_a_tile() -> None:
    label = decode_map_label(0, _label("Rimmington", 8, 2960, 3222))
    assert label.name == "Rimmington"
    assert (label.x, label.y) == (2960, 3222)
    assert label.rank == 8


def test_a_two_line_name_reads_as_one_line() -> None:
    assert decode_map_label(0, _label("Baxtorian<br>Falls", 8, 2515, 3462)).name == (
        "Baxtorian Falls"
    )


def test_the_rank_says_whether_the_map_draws_it_large() -> None:
    assert decode_map_label(0, _label("Ape Atoll", 10, 2755, 2755)).is_wide is True
    assert decode_map_label(0, _label("Clocktower", 8, 2573, 3242)).is_wide is False


def test_a_label_carrying_something_after_the_tile_is_refused() -> None:
    import pytest

    with pytest.raises(UnknownOpcode):
        decode_map_label(7, _label("Somewhere", 8, 3200, 3200, follower=1))


def test_a_rank_outside_the_three_the_map_draws_is_refused() -> None:
    import pytest

    with pytest.raises(UnknownOpcode) as caught:
        decode_map_label(7, _label("Somewhere", 3, 3200, 3200))
    assert "map label 7" in str(caught.value)


def test_a_label_that_runs_out_of_bytes_is_refused() -> None:
    import pytest

    from wiki_api.pipeline.cache.errors import TruncatedDefinition

    with pytest.raises(TruncatedDefinition):
        decode_map_label(7, b"Somewhere\0\x08")
