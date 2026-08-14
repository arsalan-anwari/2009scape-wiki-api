"""Answer which named place a tile belongs to.

Two tiers: the smallest place whose tiles hold the point, else the nearest place
within one map square. An underground tile is retried as the surface beneath it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.identity import EntityKey
from wiki_api.domain.space import Area, Coordinate

if TYPE_CHECKING:
    from collections.abc import Sequence

REACH: Final = 64
UNDERGROUND_FLOOR: Final = 6400
SURFACE_PLANE: Final = 0


class Place(BaseModel):
    """One named place, with whatever the sources could say about where it is."""

    model_config = ConfigDict(frozen=True)

    key: EntityKey
    bounds: Area | None = None
    centre: Coordinate | None = None
    rank: int = Field(default=0, ge=0)

    @property
    def size(self) -> int:
        """How many tiles this place claims, which is what makes the inner one win."""
        if self.bounds is None:
            return 0
        return (self.bounds.max_x - self.bounds.min_x + 1) * (
            self.bounds.max_y - self.bounds.min_y + 1
        )

    @property
    def point(self) -> Coordinate | None:
        """The one tile that stands for this place, whichever source gave it."""
        if self.centre is not None:
            return self.centre
        return None if self.bounds is None else self.bounds.centre

    def holds(self, point: Coordinate) -> bool:
        return self.bounds is not None and self.bounds.contains(point)

    def away_from(self, point: Coordinate) -> int | None:
        """How far this place's point is from a tile, or nothing when it has none."""
        if self.centre is None:
            return None
        return max(abs(self.centre.x - point.x), abs(self.centre.y - point.y))


class Gazetteer:
    """The places a tile can belong to, asked smallest extent first."""

    def __init__(self, places: Sequence[Place] = (), reach: int = REACH) -> None:
        self._reach = reach
        self._bounded = tuple(
            sorted(
                (place for place in places if place.bounds is not None),
                key=lambda place: (place.size, place.key.id),
            )
        )
        self._pointed = tuple(
            sorted(
                (place for place in places if place.centre is not None),
                key=lambda place: (place.rank, place.key.id),
            )
        )
        self._all = tuple(sorted(places, key=lambda place: place.key.id))

    def __len__(self) -> int:
        return len(self._all)

    @property
    def bounded(self) -> int:
        """How many places carry real tiles rather than only a point."""
        return len(self._bounded)

    def holding(self, point: Coordinate) -> EntityKey | None:
        """The place a tile belongs to, or nothing when none is near enough."""
        for asked in _asked_about(point):
            found = self._containing(asked) or self._nearest(asked)
            if found is not None:
                return found
        return None

    def within(self, area: Area) -> tuple[EntityKey, ...]:
        """Every place whose own tile falls inside these tiles, lowest id first."""
        found = [
            place.key
            for place in self._all
            if place.point is not None and area.contains(place.point)
        ]
        return tuple(sorted(found, key=lambda key: key.id))

    def _containing(self, point: Coordinate) -> EntityKey | None:
        for place in self._bounded:
            if place.holds(point):
                return place.key
        return None

    def _nearest(self, point: Coordinate) -> EntityKey | None:
        best: tuple[int, int, int] | None = None
        found: EntityKey | None = None
        for place in self._pointed:
            away = place.away_from(point)
            if away is None or away > self._reach:
                continue
            scored = (away, place.rank, place.key.id)
            if best is None or scored < best:
                best, found = scored, place.key
        return found


def _asked_about(point: Coordinate) -> tuple[Coordinate, ...]:
    """The tile itself, then the surface tile it sits beneath when it is underground."""
    asked = Coordinate(x=point.x, y=point.y, plane=SURFACE_PLANE)
    if point.y < UNDERGROUND_FLOOR:
        return (asked,)
    return (
        asked,
        Coordinate(x=point.x, y=point.y - UNDERGROUND_FLOOR, plane=SURFACE_PLANE),
    )


# test cases


def _key(number: int) -> EntityKey:
    from wiki_api.domain.identity import EntityType

    return EntityKey(type=EntityType.LOCATION, id=number)


def _bounded(number: int, region: int) -> Place:
    return Place(key=_key(number), bounds=Area.of_region(region))


def _pointed(number: int, x: int, y: int, rank: int = 8) -> Place:
    return Place(key=_key(number), centre=Coordinate(x=x, y=y), rank=rank)


def test_a_tile_inside_a_places_tiles_belongs_to_it() -> None:
    found = Gazetteer([_bounded(1, 12850)])
    assert found.holding(Coordinate(x=3222, y=3218)) == _key(1)
    assert found.bounded == 1


def test_the_smaller_of_two_nested_extents_wins() -> None:
    wide = Place(
        key=_key(1), bounds=Area(min_x=3200, min_y=3200, max_x=3400, max_y=3400)
    )
    found = Gazetteer([wide, _bounded(2, 12850)])
    assert found.holding(Coordinate(x=3222, y=3218)) == _key(2)


def test_a_tile_outside_every_extent_takes_the_nearest_point() -> None:
    found = Gazetteer([_pointed(1, 3222, 3218), _pointed(2, 2960, 3222)])
    assert found.holding(Coordinate(x=3240, y=3230)) == _key(1)


def test_a_point_further_off_than_one_map_square_reaches_nothing() -> None:
    found = Gazetteer([_pointed(1, 3222, 3218)])
    assert found.holding(Coordinate(x=3222 + REACH + 1, y=3218)) is None


def test_tiles_beat_a_nearer_point() -> None:
    found = Gazetteer([_bounded(1, 12850), _pointed(2, 3222, 3218)])
    assert found.holding(Coordinate(x=3210, y=3210)) == _key(1)


def test_a_dungeon_tile_belongs_to_the_place_above_it() -> None:
    found = Gazetteer([_bounded(1, 12850)])
    assert found.holding(Coordinate(x=3222, y=3218 + UNDERGROUND_FLOOR)) == _key(1)


def test_an_underground_place_of_its_own_wins_over_the_surface_above_it() -> None:
    below = Coordinate(x=3222, y=3218 + UNDERGROUND_FLOOR)
    found = Gazetteer(
        [_bounded(1, 12850), Place(key=_key(2), bounds=Area.of_region(below.region_id))]
    )
    assert found.holding(below) == _key(2)


def test_the_instanced_band_is_not_read_as_a_dungeon() -> None:
    found = Gazetteer([_bounded(1, 12850)])
    assert found.holding(Coordinate(x=3222, y=4500)) is None


def test_two_points_the_same_distance_away_are_broken_by_how_large_they_draw() -> None:
    found = Gazetteer([_pointed(1, 3200, 3200, rank=10), _pointed(2, 3240, 3200)])
    assert found.holding(Coordinate(x=3220, y=3200)) == _key(2)


def test_a_place_with_neither_tiles_nor_a_point_holds_nothing() -> None:
    found = Gazetteer([Place(key=_key(1))])
    assert len(found) == 1
    assert found.bounded == 0
    assert found.holding(Coordinate(x=3222, y=3218)) is None


def test_every_place_standing_inside_some_tiles_is_named() -> None:
    found = Gazetteer([_pointed(2, 3222, 3218), _pointed(1, 3240, 3230)])
    assert found.within(Area.of_region(12850)) == (_key(1), _key(2))


def test_a_place_outside_the_tiles_is_not_named_however_near_it_is() -> None:
    just_outside = Area.of_region(12850).max_x + 1
    found = Gazetteer([_pointed(1, just_outside, 3218)])
    assert found.within(Area.of_region(12850)) == ()


def test_a_place_with_tiles_and_no_point_stands_at_the_middle_of_them() -> None:
    found = Gazetteer([_bounded(1, 12850)])
    assert found.within(Area.of_region(12850)) == (_key(1),)


def test_a_place_standing_nowhere_is_inside_nothing() -> None:
    assert Gazetteer([Place(key=_key(1))]).within(Area.of_region(12850)) == ()


def test_a_tile_above_the_ground_floor_is_asked_about_on_the_surface() -> None:
    found = Gazetteer([_bounded(1, 12850)])
    assert found.holding(Coordinate(x=3222, y=3218, plane=2)) == _key(1)
