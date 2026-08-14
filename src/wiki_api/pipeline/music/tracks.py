"""Read the game's own list of music, and the partition where each piece plays."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.space import Area
from wiki_api.pipeline.music.errors import TracksUnreadable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

TRACK = re.compile(
    r"arrayId=(?P<array>\d+), "
    r"trackset=Trackset: (?P<trackset>.*?), , "
    r"fileId=(?P<file>\d+), "
    r"name=(?P<name>.*?), "
    r"unlock=(?P<unlock>.*?)\]"
)
UNDEFINED_TRACKSET: Final = '"Only defined"'
NEVER_UNLOCKED: Final = "not unlockable"


class Track(BaseModel):
    """One music track as the dump states it, prose and all."""

    model_config = ConfigDict(frozen=True)

    file_id: int = Field(ge=0)
    array_id: int = Field(ge=0)
    name: str
    trackset: str
    unlock: str

    @property
    def is_placeholder(self) -> bool:
        """Whether this row stands in for a track rather than describing one."""
        return not self.name or self.unlock.strip().lower().startswith(NEVER_UNLOCKED)

    @property
    def set_name(self) -> str:
        """The set the game groups this track into, empty for the placeholder set."""
        return "" if self.trackset == UNDEFINED_TRACKSET else self.trackset.strip()

    @property
    def note(self) -> str:
        """The unlock sentence with its full stop taken off."""
        return self.unlock.strip().rstrip(".")


class MusicRegion(BaseModel):
    """One map region, and the track the partition says plays over it."""

    model_config = ConfigDict(frozen=True)

    region: int = Field(ge=0)
    track: int = Field(ge=0)

    @property
    def area(self) -> Area:
        return Area.of_region(self.region)


def read_tracks(text: str, origin: str) -> tuple[Track, ...]:
    """Read every track the dump describes, placeholder rows included."""
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


def read_regions(rows: Sequence[Mapping[str, Any]]) -> tuple[MusicRegion, ...]:
    """Read the partition as one region per row, in region order."""
    found: dict[int, MusicRegion] = {}
    for row in rows:
        region = _number(row.get("region"))
        track = _number(row.get("id"))
        if region is None or track is None or region in found:
            continue
        found[region] = MusicRegion(region=region, track=track)
    return tuple(found[region] for region in sorted(found))


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
    'TrackDefinition [arrayId=3, trackset=Trackset: "Only defined", , fileId=177, '
    "name=, unlock=not unlockable!]\n"
)


def test_a_dump_line_becomes_a_track() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert len(tracks) == 4
    assert tracks[0].name == "Adventure"
    assert tracks[0].trackset == "Varrock"
    assert tracks[1].file_id == 50


def test_a_row_standing_in_for_a_track_says_so() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert [track.is_placeholder for track in tracks] == [False, False, False, True]


def test_the_placeholder_set_reads_as_no_set_at_all() -> None:
    tracks = read_tracks(DUMP, "dump")
    assert tracks[0].set_name == "Varrock"
    assert tracks[2].set_name == ""


def test_the_unlock_sentence_keeps_its_words_and_loses_its_full_stop() -> None:
    assert read_tracks(DUMP, "dump")[0].note == "at Varrock Palace"


def test_a_dump_that_says_nothing_is_refused() -> None:
    import pytest

    with pytest.raises(TracksUnreadable):
        read_tracks("nothing here", "dump")


def test_a_partition_row_becomes_a_region_carrying_tiles() -> None:
    regions = read_regions([{"region": "12850", "id": "177"}])
    assert len(regions) == 1
    assert regions[0].track == 177
    assert regions[0].area.min_x == 3200
    assert regions[0].area.max_y == 3263


def test_the_same_region_declared_twice_is_read_once() -> None:
    regions = read_regions([{"region": 12850, "id": 1}, {"region": 12850, "id": 2}])
    assert len(regions) == 1
    assert regions[0].track == 1


def test_regions_come_back_in_a_stable_order() -> None:
    regions = read_regions([{"region": 12851, "id": 1}, {"region": 12850, "id": 2}])
    assert [region.region for region in regions] == [12850, 12851]


def test_a_row_that_is_not_a_pair_of_numbers_is_skipped() -> None:
    assert read_regions([{"region": "north", "id": "1"}, {}]) == ()
