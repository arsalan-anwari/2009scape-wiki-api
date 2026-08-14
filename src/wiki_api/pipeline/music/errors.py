"""What can go wrong while reading the game's own list of music."""

from __future__ import annotations


class MusicReadError(ValueError):
    """A source describing the game's music could not be read."""


class TracksUnreadable(MusicReadError):
    """The music dump held no track, so nothing describes the game's music."""

    def __init__(self, origin: str) -> None:
        super().__init__(f"{origin} names no track")
        self.origin = origin


# test cases


def test_an_unreadable_dump_names_itself() -> None:
    assert "music.txt" in str(TracksUnreadable("music.txt"))
