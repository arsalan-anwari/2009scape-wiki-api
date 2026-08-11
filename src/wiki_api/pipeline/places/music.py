"""Read the game's music partition into named regions.

`music_regions.json` says which track plays in which region and the track dump says
where each track unlocks, which together give a region a name and a set of tiles.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.space import Area
from wiki_api.pipeline.places.errors import TracksUnreadable

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

TRACK = re.compile(
    r"arrayId=(?P<array>\d+), "
    r"trackset=Trackset: (?P<trackset>.*?), , "
    r"fileId=(?P<file>\d+), "
    r"name=(?P<name>.*?), "
    r"unlock=(?P<unlock>.*?)\]"
)
UNDEFINED_TRACKSET: Final = '"Only defined"'
LEADING = re.compile(r"^(?:at|in|on|to)\s+(?:the\s+)?", re.IGNORECASE)
SCOPED: Final = ("during", "while", "not unlockable")
SURFACE_CEILING: Final = 6400


class Track(BaseModel):
    """One music track, and the sentence saying where a player first hears it."""

    model_config = ConfigDict(frozen=True)

    file_id: int = Field(ge=0)
    array_id: int = Field(ge=0)
    name: str
    trackset: str
    unlock: str

    @property
    def is_grouped(self) -> bool:
        """Whether the set names part of the world rather than a placeholder."""
        return self.trackset != UNDEFINED_TRACKSET and bool(self.trackset)

    @property
    def place(self) -> str:
        """The unlock sentence reduced to the place inside it, or empty when the
        sentence is about an event rather than somewhere a player can stand.
        """
        said = self.unlock.strip().rstrip(".")
        if not said or said.lower().startswith(SCOPED):
            return ""
        return LEADING.sub("", said).strip()


class PlacedRegion(BaseModel):
    """One region of the map, with whatever the music partition can say about it."""

    model_config = ConfigDict(frozen=True)

    region: int = Field(ge=0)
    min_x: int = Field(ge=0)
    min_y: int = Field(ge=0)
    max_x: int = Field(ge=0)
    max_y: int = Field(ge=0)
    track: int = Field(ge=0)
    track_name: str = ""
    trackset: str = ""
    unlock: str = ""
    place: str = ""

    @property
    def is_surface(self) -> bool:
        """Whether these tiles are the overworld rather than a dungeon copy of it."""
        return self.min_y < SURFACE_CEILING

    @property
    def area(self) -> Area:
        return Area(
            min_x=self.min_x, min_y=self.min_y, max_x=self.max_x, max_y=self.max_y
        )


def read_tracks(text: str, origin: str) -> tuple[Track, ...]:
    """Read every track the dump describes."""
    tracks = tuple(
        Track(
            array_id=int(found["array"]),
            file_id=int(found["file"]),
            name=found["name"].strip(),
            trackset=found["trackset"].strip(),
            unlock=found["unlock"].strip(),
        )
        for found in (match.groupdict() for match in TRACK.finditer(text))
    )
    if not tracks:
        raise TracksUnreadable(origin)
    return tracks


def read_placed_regions(
    regions: Sequence[Mapping[str, Any]], tracks: Iterable[Track]
) -> tuple[PlacedRegion, ...]:
    """Join every region to the track that plays in it, in region order."""
    by_file = {track.file_id: track for track in tracks}
    placed: dict[int, PlacedRegion] = {}
    for row in regions:
        region = _number(row.get("region"))
        track = _number(row.get("id"))
        if region is None or track is None or region in placed:
            continue
        placed[region] = _placed(region, track, by_file.get(track))
    return tuple(placed[region] for region in sorted(placed))


def _placed(region: int, track: int, found: Track | None) -> PlacedRegion:
    square = Area.of_region(region)
    return PlacedRegion(
        region=region,
        min_x=square.min_x,
        min_y=square.min_y,
        max_x=square.max_x,
        max_y=square.max_y,
        track=track,
        track_name="" if found is None else found.name,
        trackset="" if found is None or not found.is_grouped else found.trackset,
        unlock="" if found is None else found.unlock,
        place="" if found is None else found.place,
    )


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return None


# test cases


DUMP = (
    "TrackDefinition [arrayId=0, trackset=Trackset: Varrock, , fileId=177, "
    "name=Adventure, unlock=at Varrock Palace.]\n"
    "TrackDefinition [arrayId=1, trackset=Trackset: Kharidian, , fileId=50, "
    "name=Al Kharid, unlock=at Al Kharid.]\n"
    'TrackDefinition [arrayId=2, trackset=Trackset: "Only defined", , fileId=102, '
    "name=Alone, unlock=during the Golem.]\n"
)


def test_a_dump_line_becomes_a_track() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert len(tracks) == 3
    assert tracks[0].name == "Adventure"
    assert tracks[0].trackset == "Varrock"
    assert tracks[1].file_id == 50


def test_an_unlock_sentence_reduces_to_the_place_inside_it() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert tracks[0].place == "Varrock Palace"
    assert tracks[1].place == "Al Kharid"


def test_a_sentence_about_an_event_names_no_place() -> None:
    assert read_tracks(DUMP, "dump")[2].place == ""


def test_a_placeholder_set_is_not_treated_as_part_of_the_world() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert tracks[0].is_grouped is True
    assert tracks[2].is_grouped is False


def test_a_dump_that_says_nothing_is_refused() -> None:
    import pytest

    with pytest.raises(TracksUnreadable):
        read_tracks("nothing here", "dump")


def test_a_region_carries_the_tiles_and_the_words_for_them() -> None:
    placed = read_placed_regions(
        [{"region": "12850", "id": "177"}], read_tracks(DUMP, "dump")
    )
    assert len(placed) == 1
    assert placed[0].min_x == 3200
    assert placed[0].max_y == 3263
    assert placed[0].trackset == "Varrock"
    assert placed[0].place == "Varrock Palace"
    assert placed[0].is_surface is True


def test_a_region_whose_track_the_dump_never_names_still_lands() -> None:
    placed = read_placed_regions([{"region": "12850", "id": "9999"}], ())
    assert placed[0].track == 9999
    assert placed[0].place == ""


def test_a_region_underground_says_so() -> None:
    placed = read_placed_regions([{"region": (50 << 8) | 150, "id": 1}], ())
    assert placed[0].is_surface is False


def test_the_same_region_declared_twice_is_read_once() -> None:
    placed = read_placed_regions(
        [{"region": 12850, "id": 1}, {"region": 12850, "id": 2}], ()
    )
    assert len(placed) == 1
    assert placed[0].track == 1


def test_a_row_that_is_not_a_pair_of_numbers_is_skipped() -> None:
    assert read_placed_regions([{"region": "north", "id": "1"}, {}], ()) == ()
