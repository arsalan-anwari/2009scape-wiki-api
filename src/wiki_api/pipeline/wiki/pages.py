"""Turn one saved wiki page into headed sections of plain text, ids and links."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.wiki.errors import PageUnreadable

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

BODY_START: Final = "wikipage start"
BODY_STOP: Final = "wikipage stop"
HEADINGS: Final = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
IGNORED_TAGS: Final = frozenset({"script", "style", "form", "select", "button"})
IGNORED_CLASSES: Final = ("secedit", "dw__toc", "plugin-autotooltip-hidden")
LEAD_SECTION: Final = "start"
ITEM_ICON: Final = re.compile(r"item_icons/(\d+)\.png")
PAGE_LINK: Final = re.compile(r"^/wiki/([a-z0-9][a-z0-9_]*)/([a-z0-9][a-z0-9_]*)$")
CANONICAL: Final = re.compile(
    r'rel="canonical"\s+href="[^"]*?/([a-z0-9_]+)/([a-z0-9_]+)"'
)
WHITESPACE: Final = re.compile(r"\s+")
BLOCK_TAGS: Final = frozenset({"p", "li", "div", "tr", "br", "td", "th"})


class WikiSection(BaseModel):
    """One heading of a page, as text plus the ids and pages it points at."""

    model_config = ConfigDict(frozen=True)

    heading_id: str = Field(min_length=1)
    heading: str = ""
    text: str = ""
    item_ids: tuple[int, ...] = ()
    page_links: tuple[str, ...] = ()


class WikiPage(BaseModel):
    """One saved page, keyed by the id the wiki gives it."""

    model_config = ConfigDict(frozen=True)

    slug: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    title: str = ""
    sections: tuple[WikiSection, ...] = ()

    def section(self, *names: str) -> WikiSection | None:
        """The first section whose heading id is one of the names given."""
        wanted = set(names)
        return next((one for one in self.sections if one.heading_id in wanted), None)

    def sections_named(self, names: Iterable[str]) -> tuple[WikiSection, ...]:
        wanted = set(names)
        return tuple(one for one in self.sections if one.heading_id in wanted)


def read_page(source: str, origin: str) -> WikiPage:
    """Read one saved page, keeping only what sits between the content markers."""
    found = CANONICAL.search(source)
    if found is None:
        raise PageUnreadable(origin, "the page states no canonical address")
    reader = _Reader()
    reader.feed(source)
    reader.close()
    if not reader.seen_body:
        raise PageUnreadable(origin, "the page holds no content markers")
    return WikiPage(
        slug=found.group(2),
        namespace=found.group(1),
        title=reader.title,
        sections=tuple(reader.sections()),
    )


def read_pages(paths: Sequence[Path]) -> tuple[WikiPage, ...]:
    """Read every saved page given, in the order the caller listed them."""
    return tuple(
        read_page(path.read_text(encoding="utf-8", errors="replace"), path.name)
        for path in paths
    )


class _Draft:
    def __init__(self, heading_id: str) -> None:
        self.heading_id = heading_id
        self.heading = ""
        self.words: list[str] = []
        self.item_ids: list[int] = []
        self.page_links: list[str] = []


class _Reader(HTMLParser):
    """Collect the text, item ids and page links of each headed section."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.seen_body = False
        self.title = ""
        self._in_body = False
        self._in_title = False
        self._drafts: list[_Draft] = []
        self._ignore_depth = 0
        self._ignore_tag: str | None = None
        self._heading: str | None = None

    def sections(self) -> tuple[WikiSection, ...]:
        read = (
            WikiSection(
                heading_id=draft.heading_id,
                heading=draft.heading.strip(),
                text=WHITESPACE.sub(" ", " ".join(draft.words)).strip(),
                item_ids=tuple(dict.fromkeys(draft.item_ids)),
                page_links=tuple(dict.fromkeys(draft.page_links)),
            )
            for draft in self._drafts
        )
        return tuple(one for one in read if one.text or one.item_ids or one.page_links)

    def handle_comment(self, data: str) -> None:
        marker = data.strip()
        if marker == BODY_START:
            self._in_body = True
            self.seen_body = True
            self._drafts.append(_Draft(LEAD_SECTION))
        elif marker == BODY_STOP:
            self._in_body = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
            return
        if not self._in_body:
            return
        if self._ignore_depth:
            if tag == self._ignore_tag:
                self._ignore_depth += 1
            return
        held = dict(attrs)
        if tag in IGNORED_TAGS or _is_ignored(held.get("class")):
            self._ignore_tag = tag
            self._ignore_depth = 1
            return
        if tag in HEADINGS and held.get("id"):
            self._drafts.append(_Draft(str(held["id"])))
            self._heading = tag
            return
        if tag in BLOCK_TAGS:
            self._word(" ")
        self._read_attributes(held)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if self._ignore_depth and tag == self._ignore_tag:
            self._ignore_depth -= 1
            if not self._ignore_depth:
                self._ignore_tag = None
            return
        if self._heading == tag:
            self._heading = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if not self._in_body or self._ignore_depth or not self._drafts:
            return
        if self._heading is not None:
            self._drafts[-1].heading += data
            return
        self._word(data)

    def _word(self, data: str) -> None:
        if self._drafts and data.strip():
            self._drafts[-1].words.append(data)
        elif self._drafts:
            self._drafts[-1].words.append(" ")

    def _read_attributes(self, held: dict[str, str | None]) -> None:
        if not self._drafts:
            return
        draft = self._drafts[-1]
        for value in (held.get("src"), held.get("href")):
            if value:
                draft.item_ids.extend(int(one) for one in ITEM_ICON.findall(value))
        address = held.get("href")
        if address is None:
            return
        linked = PAGE_LINK.match(address.split("?", 1)[0].split("#", 1)[0])
        if linked is not None:
            draft.page_links.append(f"{linked.group(1)}/{linked.group(2)}")


def _is_ignored(classes: str | None) -> bool:
    if not classes:
        return False
    return any(marker in classes for marker in IGNORED_CLASSES)


# test cases

SAMPLE: Final = """
<html><head><title>quest_guides:cooks_assistant [2009scape Wiki]</title>
<link rel="canonical" href="https://cdn.2009scape.org/wiki/quest_guides/cooks_assistant"/>
</head><body>
<!-- wikipage start -->
<p>An opening line.</p>
<h2 id="start_point">Start Point</h2>
<div class="level2"><p><strong>Lumbridge Castle</strong> - Kitchen.</p></div>
<div class="secedit"><form><button>Edit</button></form></div>
<h3 id="requirements">Requirements</h3>
<ul><li><img src="/wiki/_media/quest_guides/item_icons/1927.png?w=36"/>
 - <strong>Bucket of milk</strong></li>
<li><a href="/wiki/quest_guides/rune_mysteries">Rune Mysteries</a></li></ul>
<script>var x = 1;</script>
<!-- wikipage stop -->
</body></html>
"""


def test_a_saved_page_reads_as_headed_sections() -> None:
    page = read_page(SAMPLE, "cooks_assistant.html")
    assert page.slug == "cooks_assistant"
    assert page.namespace == "quest_guides"
    assert page.title.startswith("quest_guides:cooks_assistant")
    assert [one.heading_id for one in page.sections] == [
        "start",
        "start_point",
        "requirements",
    ]


def test_a_section_keeps_its_words_and_drops_the_page_furniture() -> None:
    page = read_page(SAMPLE, "cooks_assistant.html")
    start = page.section("start_point")
    assert start is not None
    assert start.heading == "Start Point"
    assert start.text == "Lumbridge Castle - Kitchen."
    assert "Edit" not in start.text


def test_a_section_reads_the_item_ids_its_icons_name() -> None:
    page = read_page(SAMPLE, "cooks_assistant.html")
    requirements = page.section("requirements")
    assert requirements is not None
    assert requirements.item_ids == (1927,)
    assert requirements.page_links == ("quest_guides/rune_mysteries",)


def test_a_script_never_becomes_text() -> None:
    page = read_page(SAMPLE, "cooks_assistant.html")
    assert all("var x" not in one.text for one in page.sections)


def test_a_page_with_no_content_markers_is_refused() -> None:
    import pytest

    with pytest.raises(PageUnreadable):
        read_page(
            '<link rel="canonical" href="/wiki/quest_guides/x"/><p>nothing</p>',
            "x.html",
        )


def test_a_page_that_states_no_address_is_refused() -> None:
    import pytest

    with pytest.raises(PageUnreadable):
        read_page("<html><body>nothing</body></html>", "x.html")


def test_asking_for_a_section_by_any_of_its_spellings_finds_it() -> None:
    page = read_page(SAMPLE, "cooks_assistant.html")
    assert page.section("required", "requirements") is not None
    assert page.section("nothing_like_this") is None
    assert len(page.sections_named(("start_point", "requirements"))) == 2
