"""What can go wrong while reading a saved wiki page."""

from __future__ import annotations


class WikiReadError(ValueError):
    """A saved page could not be read."""


class PageUnreadable(WikiReadError):
    """One page did not hold what every saved page holds."""

    def __init__(self, origin: str, reason: str) -> None:
        super().__init__(f"{origin} could not be read: {reason}")
        self.origin = origin
        self.reason = reason


class PagesMissing(WikiReadError):
    """The directory of saved pages is not where staging was told to look."""

    def __init__(self, directory: str) -> None:
        super().__init__(f"no saved wiki pages under {directory}")
        self.directory = directory


# test cases


def test_an_unreadable_page_names_itself_and_the_reason() -> None:
    error = PageUnreadable("cooks_assistant.html", "no content markers")
    assert "cooks_assistant.html" in str(error)
    assert error.reason == "no content markers"


def test_a_missing_directory_names_where_it_looked() -> None:
    assert "under /tmp/pages" in str(PagesMissing("/tmp/pages"))
