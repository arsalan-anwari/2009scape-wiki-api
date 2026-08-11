"""Positions and areas on the game map."""

from __future__ import annotations

from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.vocabulary import GameEnum

REGION_SHIFT: Final = 6
REGION_STRIDE: Final = 8
REGION_SIDE: Final = 1 << REGION_SHIFT
REGION_MASK: Final = (1 << REGION_STRIDE) - 1
MAX_PLANE: Final = 3
COORDINATE_SEPARATOR: Final = ":"


class LocationKind(GameEnum):
    """What sort of place a location is."""

    CITY = "city"
    TOWN = "town"
    VILLAGE = "village"
    BUILDING = "building"
    DUNGEON = "dungeon"
    AREA = "area"
    ISLAND = "island"


class SpawnKind(GameEnum):
    """Why something stands where it stands."""

    NPC_SPAWN = "npc_spawn"
    GROUND_SPAWN = "ground_spawn"
    SHOP_FRONT = "shop_front"
    QUEST_START = "quest_start"
    BUILT_IN = "built_in"


class Coordinate(BaseModel):
    """One tile on the map."""

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    plane: int = Field(default=0, ge=0, le=MAX_PLANE)

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.plane))

    def __str__(self) -> str:
        return COORDINATE_SEPARATOR.join((str(self.x), str(self.y), str(self.plane)))

    @property
    def region_id(self) -> int:
        return ((self.x >> REGION_SHIFT) << REGION_STRIDE) | (self.y >> REGION_SHIFT)


class Area(BaseModel):
    """A rectangle of tiles on a single plane."""

    model_config = ConfigDict(frozen=True)

    min_x: int = Field(ge=0)
    min_y: int = Field(ge=0)
    max_x: int = Field(ge=0)
    max_y: int = Field(ge=0)
    plane: int = Field(default=0, ge=0, le=MAX_PLANE)

    @model_validator(mode="after")
    def _check_extent(self) -> Self:
        if self.max_x < self.min_x or self.max_y < self.min_y:
            raise ValueError("an area cannot end before it starts")
        return self

    @classmethod
    def of_region(cls, region_id: int) -> Self:
        """The square of tiles the game addresses under one region number."""
        west = (region_id >> REGION_STRIDE) << REGION_SHIFT
        south = (region_id & REGION_MASK) << REGION_SHIFT
        return cls(
            min_x=west,
            min_y=south,
            max_x=west + REGION_SIDE - 1,
            max_y=south + REGION_SIDE - 1,
        )

    def joined(self, other: Area) -> Self:
        """The smallest rectangle holding both, which is how an area of many regions
        gets its extent.
        """
        return type(self)(
            min_x=min(self.min_x, other.min_x),
            min_y=min(self.min_y, other.min_y),
            max_x=max(self.max_x, other.max_x),
            max_y=max(self.max_y, other.max_y),
            plane=self.plane,
        )

    @property
    def centre(self) -> Coordinate:
        return Coordinate(
            x=(self.min_x + self.max_x) // 2,
            y=(self.min_y + self.max_y) // 2,
            plane=self.plane,
        )

    def contains(self, point: Coordinate) -> bool:
        return (
            point.plane == self.plane
            and self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
        )


# test cases


def test_a_coordinate_renders_the_stable_form_a_spawn_edge_is_keyed_by() -> None:
    assert str(Coordinate(x=2273, y=4698, plane=0)) == "2273:4698:0"


def test_the_region_follows_the_games_own_addressing() -> None:
    assert Coordinate(x=3200, y=3200).region_id == 12850
    assert Coordinate(x=2273, y=4698).region_id == 9033


def test_two_points_in_the_same_region_share_a_region_id() -> None:
    first = Coordinate(x=3200, y=3200)
    second = Coordinate(x=3230, y=3240)
    assert first.region_id == second.region_id


def test_a_plane_above_the_roof_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        Coordinate(x=3200, y=3200, plane=MAX_PLANE + 1)


def test_coordinates_compare_by_value_and_are_hashable() -> None:
    first = Coordinate(x=3200, y=3200)
    second = Coordinate(x=3200, y=3200)
    assert first == second
    assert len({first, second}) == 1


def test_a_region_number_turns_back_into_the_square_it_addresses() -> None:
    square = Area.of_region(12850)
    assert (square.min_x, square.min_y) == (3200, 3200)
    assert (square.max_x, square.max_y) == (3263, 3263)
    assert square.contains(Coordinate(x=3222, y=3218))


def test_every_tile_in_a_square_agrees_on_the_region_it_came_from() -> None:
    square = Area.of_region(9033)
    assert Coordinate(x=square.min_x, y=square.min_y).region_id == 9033
    assert Coordinate(x=square.max_x, y=square.max_y).region_id == 9033


def test_two_squares_join_into_the_rectangle_that_holds_both() -> None:
    joined = Area.of_region(12850).joined(Area.of_region(12851))
    assert (joined.min_x, joined.min_y) == (3200, 3200)
    assert (joined.max_x, joined.max_y) == (3263, 3327)


def test_an_area_knows_its_centre_and_what_falls_inside_it() -> None:
    area = Area(min_x=3200, min_y=3200, max_x=3210, max_y=3220)
    assert area.centre == Coordinate(x=3205, y=3210)
    assert area.contains(Coordinate(x=3205, y=3210)) is True
    assert area.contains(Coordinate(x=3300, y=3210)) is False


def test_an_area_does_not_reach_across_planes() -> None:
    area = Area(min_x=3200, min_y=3200, max_x=3210, max_y=3220)
    assert area.contains(Coordinate(x=3205, y=3210, plane=1)) is False


def test_an_inverted_area_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        Area(min_x=3210, min_y=3200, max_x=3200, max_y=3220)
    with pytest.raises(ValueError):
        Area(min_x=3200, min_y=3220, max_x=3210, max_y=3200)


def test_a_single_tile_area_is_valid() -> None:
    area = Area(min_x=3200, min_y=3200, max_x=3200, max_y=3200)
    assert area.centre == Coordinate(x=3200, y=3200)
    assert area.contains(area.centre) is True
