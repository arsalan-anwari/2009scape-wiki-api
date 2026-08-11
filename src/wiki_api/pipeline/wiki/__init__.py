"""Read the community wiki's saved pages into parts a fact can be checked in."""

from wiki_api.pipeline.wiki.pages import (
    WikiPage,
    WikiSection,
    read_page,
    read_pages,
)

__all__ = ["WikiPage", "WikiSection", "read_page", "read_pages"]
