"""Decode index 5, transcribed from the game's own LandscapeParser."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.cache.buffer import ByteReader

KIND: Final = "landscape"
REGION_SIZE: Final = 64
TILE_MASK: Final = 0x3F
PLANE_SHIFT: Final = 12
LOCAL_X_SHIFT: Final = 6
ROTATION_MASK: Final = 0x3
TYPE_SHIFT: Final = 2
REGION_X_SHIFT: Final = 8
REGION_ID_MASK: Final = 0xFF
LANDSCAPE_NAME: Final = "l{region_x}_{region_y}"


class Placement(BaseModel):
    """One object standing on one tile."""

    model_config = ConfigDict(frozen=True)

    object_id: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    plane: int = Field(ge=0)
    type: int = Field(ge=0)
    rotation: int = Field(ge=0)


def region_name(region_id: int) -> str:
    """The archive name the game asks index 5 for, for one region."""
    return LANDSCAPE_NAME.format(
        region_x=region_id >> REGION_X_SHIFT, region_y=region_id & REGION_ID_MASK
    )


def decode_landscape(region_id: int, data: bytes) -> tuple[Placement, ...]:
    """Read every object placed in one region, in the order the region declares them."""
    reader = ByteReader(data, kind=KIND, identity=region_id)
    base_x = (region_id >> REGION_X_SHIFT) * REGION_SIZE
    base_y = (region_id & REGION_ID_MASK) * REGION_SIZE
    found: list[Placement] = []
    object_id = -1
    while True:
        step = reader.big_smart()
        if step == 0:
            break
        object_id += step
        location = 0
        while True:
            offset = reader.smart()
            if offset == 0:
                break
            location += offset - 1
            configuration = reader.unsigned_byte()
            found.append(
                Placement(
                    object_id=object_id,
                    x=base_x + ((location >> LOCAL_X_SHIFT) & TILE_MASK),
                    y=base_y + (location & TILE_MASK),
                    plane=location >> PLANE_SHIFT,
                    type=configuration >> TYPE_SHIFT,
                    rotation=configuration & ROTATION_MASK,
                )
            )
    return tuple(found)


# test cases


def _smart(value: int) -> bytes:
    if value <= 127:
        return bytes([value])
    written = value + 32768
    return bytes([written >> 8, written & 0xFF])


def _region(*groups: tuple[int, tuple[tuple[int, int, int, int], ...]]) -> bytes:
    out = bytearray()
    previous_object = -1
    for object_id, tiles in groups:
        out += _smart(object_id - previous_object)
        previous_object = object_id
        previous_location = 0
        for local_x, local_y, plane, configuration in tiles:
            location = (plane << PLANE_SHIFT) | (local_x << LOCAL_X_SHIFT) | local_y
            out += _smart(location - previous_location + 1)
            previous_location = location
            out.append(configuration)
        out.append(0)
    out.append(0)
    return bytes(out)


def test_a_region_decodes_every_object_it_places() -> None:
    found = decode_landscape(
        12850,
        _region(
            (1276, ((1, 2, 0, 0b000110),)),
        ),
    )
    assert len(found) == 1
    placed = found[0]
    assert placed.object_id == 1276
    assert placed.type == 1
    assert placed.rotation == 2


def test_a_placement_carries_the_world_tile_not_the_local_one() -> None:
    found = decode_landscape(
        12850,
        _region(
            (1, ((1, 2, 0, 0),)),
        ),
    )
    assert found[0].x == (12850 >> 8) * 64 + 1
    assert found[0].y == (12850 & 0xFF) * 64 + 2


def test_a_placement_above_the_ground_keeps_its_plane() -> None:
    found = decode_landscape(
        12850,
        _region(
            (1, ((0, 0, 2, 0),)),
        ),
    )
    assert found[0].plane == 2


def test_object_ids_and_tiles_are_both_read_as_steps() -> None:
    found = decode_landscape(
        12850,
        _region(
            (10, ((0, 0, 0, 0), (0, 1, 0, 0))),
            (12, ((5, 5, 0, 0),)),
        ),
    )
    assert [placed.object_id for placed in found] == [10, 10, 12]
    assert [placed.y % 64 for placed in found] == [0, 1, 5]


def test_a_region_that_places_nothing_is_empty() -> None:
    assert decode_landscape(12850, bytes([0])) == ()


def test_the_archive_name_matches_the_one_the_game_asks_for() -> None:
    assert region_name(12850) == "l50_50"
    assert region_name(0) == "l0_0"
