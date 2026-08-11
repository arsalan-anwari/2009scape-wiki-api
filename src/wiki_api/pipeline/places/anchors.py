"""Read the community's teleport list, which names a point rather than an extent."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Iterator

NAMED_FIRST = re.compile(r"^(?P<name>.+?)\s*::tele\s+(?P<x>\d+)\s*[, ]\s*(?P<y>\d+)$")
NAMED_LAST = re.compile(r"^::tele\s+(?P<x>\d+)\s+(?P<y>\d+)\s*=\s*(?P<name>.+)$")
ASSIGNED = re.compile(r"^(?P<name>[^=]+?)\s*=\s*(?P<x>\d+)\s+(?P<y>\d+)$")
DASHED = re.compile(r"^(?P<x>\d+)\s+(?P<y>\d+)\s*-\s*(?P<name>.+)$")
SPELLINGS: Final = (NAMED_FIRST, NAMED_LAST, ASSIGNED, DASHED)
NOISE = re.compile(r"[^a-z0-9]+")
MAX_TILE: Final = 1 << 15


class Anchor(BaseModel):
    """One named point somebody teleported to and wrote down."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    folded: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class AnchorSheet(BaseModel):
    """Everything the teleport list gave up, and how much of it it did not."""

    model_config = ConfigDict(frozen=True)

    anchors: tuple[Anchor, ...] = ()
    lines: int = 0
    unread: int = 0

    def named(self, name: str) -> Anchor | None:
        """Find the point somebody wrote down for this name, however they spelt it."""
        wanted = folded(name)
        for anchor in self.anchors:
            if anchor.folded == wanted:
                return anchor
        return None


def folded(name: str) -> str:
    """Reduce a name to what survives one person typing it and another correcting it."""
    return NOISE.sub("", name.lower())


def read_anchors(text: str) -> AnchorSheet:
    """Read every point the list states, keeping the first spelling of each name."""
    seen: dict[str, Anchor] = {}
    lines = 0
    unread = 0
    for line in text.splitlines():
        said = line.strip()
        if not said:
            continue
        lines += 1
        anchor = _anchor(said)
        if anchor is None:
            unread += 1
            continue
        seen.setdefault(anchor.folded, anchor)
    return AnchorSheet(
        anchors=tuple(seen[key] for key in sorted(seen)), lines=lines, unread=unread
    )


def _anchor(said: str) -> Anchor | None:
    for found in _matches(said):
        name = found["name"].strip()
        x, y = int(found["x"]), int(found["y"])
        if not name or not folded(name) or x >= MAX_TILE or y >= MAX_TILE:
            return None
        return Anchor(name=name, folded=folded(name), x=x, y=y)
    return None


def _matches(said: str) -> Iterator[dict[str, str]]:
    for spelling in SPELLINGS:
        match = spelling.match(said)
        if match is not None:
            yield match.groupdict()
            return


# test cases


LIST = """
Varrock ::tele 3210,3424
Lumbridge ::tele 3222,3218
::tele 2861 3165 = volcano
falador = 2964 3378
3429 3538 - Slayer Tower
Keldagram ::tele 2937,9999 (and run north for a little while)

"""


def test_every_spelling_in_the_list_is_read() -> None:
    sheet = read_anchors(LIST)
    assert {anchor.name for anchor in sheet.anchors} == {
        "Varrock",
        "Lumbridge",
        "volcano",
        "falador",
        "Slayer Tower",
    }


def test_a_line_nobody_can_parse_is_counted_rather_than_guessed_at() -> None:
    sheet = read_anchors(LIST)
    assert sheet.unread == 1
    assert sheet.lines == 6


def test_a_point_comes_back_under_however_it_was_spelt() -> None:
    sheet = read_anchors(LIST)
    found = sheet.named("Falador")
    assert found is not None
    assert (found.x, found.y) == (2964, 3378)


def test_a_name_nobody_wrote_down_answers_with_nothing() -> None:
    assert read_anchors(LIST).named("Prifddinas") is None


def test_the_first_spelling_of_a_name_is_the_one_kept() -> None:
    sheet = read_anchors("Varrock ::tele 1,2\nvarrock = 3 4\n")
    assert len(sheet.anchors) == 1
    assert (sheet.anchors[0].x, sheet.anchors[0].y) == (1, 2)


def test_a_point_off_the_map_is_not_read_as_one() -> None:
    assert read_anchors("Somewhere ::tele 99999,3 \n").anchors == ()


def test_names_come_back_in_a_stable_order() -> None:
    once = [anchor.name for anchor in read_anchors(LIST).anchors]
    again = [anchor.name for anchor in read_anchors(LIST).anchors]
    assert once == again == sorted(once, key=folded)
