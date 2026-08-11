"""What can go wrong while reading the sources that name a part of the map."""

from __future__ import annotations


class PlaceReadError(ValueError):
    """A source that names part of the map could not be read."""


class TracksUnreadable(PlaceReadError):
    """The music dump held no track, so nothing can name a region."""

    def __init__(self, origin: str) -> None:
        super().__init__(f"{origin} names no track")
        self.origin = origin


# test cases


def test_an_unreadable_dump_names_itself() -> None:
    assert "music.txt" in str(TracksUnreadable("music.txt"))
