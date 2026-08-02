"""Shrink the core's answers for a reader that pays per word.

Each carries what the question needs, a count of what was left out, and the call that
would fetch it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.core import prominent_values
from wiki_api.domain.identity import EntityType
from wiki_api.domain.relationships import RELATIONSHIP_SPECS
from wiki_api.surfaces.mcp.naming import tool_name
from wiki_api.surfaces.mcp.values import labelled

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.core import (
        AttributeValue,
        Block,
        EntitySummary,
        PageDescriptor,
        Row,
        SearchResult,
        TypeInfo,
    )
    from wiki_api.domain.identity import Link
    from wiki_api.domain.page import Page

MOST_EXAMPLES: Final = 3


class Neighbour(BaseModel):
    """One thing reached over a link, and what the link itself records."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: EntityType
    id: int
    facts: dict[str, str] = Field(default_factory=dict)


class Reachable(BaseModel):
    """One way onwards from a thing: how much there is, and what to call for it."""

    model_config = ConfigDict(frozen=True)

    tool: str
    label: str
    total: int = Field(ge=0)
    examples: tuple[str, ...] = ()


class Thing(BaseModel):
    """One thing, its values worth knowing, and every way onwards from it as a count
    rather than contents.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    type: EntityType
    id: int
    slug: str
    summary: str | None = None
    facts: dict[str, str] = Field(default_factory=dict)
    same_thing_as: str | None = None
    reachable: tuple[Reachable, ...] = ()


class Related(BaseModel):
    """One page of one way onwards, and what to pass back to read the next."""

    model_config = ConfigDict(frozen=True)

    of: str
    label: str
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    neighbours: tuple[Neighbour, ...] = ()
    next_offset: int | None = None
    left_out: int = Field(default=0, ge=0)


class Candidate(BaseModel):
    """One thing a set of words turned up, named well enough to ask about."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: EntityType
    id: int = Field(ge=0)
    summary: str | None = None


class Matches(BaseModel):
    """Whatever a question turned up, and what to pass back for the rest."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    found: tuple[Candidate, ...] = ()
    next_offset: int | None = None
    data_version: str


class Sort(BaseModel):
    """One sort of thing this build knows about, and how many of them there are."""

    model_config = ConfigDict(frozen=True)

    type: EntityType
    label: str
    plural: str
    total: int = Field(ge=0)


class Sorts(BaseModel):
    """Every sort of thing that can be asked about."""

    model_config = ConfigDict(frozen=True)

    sorts: tuple[Sort, ...] = ()
    data_version: str


def thing_of(descriptor: PageDescriptor) -> Thing:
    """Shrink a whole page to what a reader would use."""
    return Thing(
        name=descriptor.entity.label,
        type=descriptor.type,
        id=descriptor.entity.id,
        slug=descriptor.entity.slug,
        summary=descriptor.description,
        facts=labelled(prominent_values(_all_values(descriptor))),
        same_thing_as=_named(descriptor.canonical),
        reachable=tuple(_reachable(block) for block in descriptor.blocks),
    )


def related_of(block: Block, of: str) -> Related:
    """Shrink one page of one way onwards."""
    return Related(
        of=of,
        label=block.label,
        total=block.rows.total,
        offset=block.rows.offset,
        neighbours=tuple(_neighbour(row) for row in block.rows.items),
        next_offset=block.rows.next_offset,
        left_out=block.suppressed,
    )


def matches_of(
    page: Page[SearchResult] | Page[EntitySummary], data_version: str
) -> Matches:
    """Shrink a listing to what it takes to ask a better question next."""
    return Matches(
        total=page.total,
        offset=page.offset,
        found=tuple(
            Candidate(
                name=summary.link.label,
                type=summary.type,
                id=summary.link.id,
                summary=summary.description,
            )
            for summary in page.items
        ),
        next_offset=page.next_offset,
        data_version=data_version,
    )


def sorts_of(
    described: Sequence[TypeInfo], totals: Mapping[EntityType, int], data_version: str
) -> Sorts:
    """List what can be asked about, and how much of each there is.

    Each sort's declared values are left out: choosing between sorts does not need
    them, and they cost more to read than the answer they lead to.
    """
    return Sorts(
        sorts=tuple(
            Sort(
                type=info.type,
                label=info.label,
                plural=info.plural,
                total=totals.get(info.type, 0),
            )
            for info in described
        ),
        data_version=data_version,
    )


def _all_values(descriptor: PageDescriptor) -> tuple[AttributeValue, ...]:
    gathered = list(descriptor.infobox)
    for section in descriptor.sections:
        gathered.extend(section.attributes)
    return tuple(gathered)


def _reachable(block: Block) -> Reachable:
    spec = RELATIONSHIP_SPECS[block.walk.rel]
    return Reachable(
        tool=tool_name(spec, block.walk.direction),
        label=block.label,
        total=block.rows.total,
        examples=tuple(row.link.label for row in block.rows.items[:MOST_EXAMPLES]),
    )


def _neighbour(row: Row) -> Neighbour:
    return Neighbour(
        name=row.link.label,
        type=row.type,
        id=row.link.id,
        facts=labelled(prominent_values(row.attributes)),
    )


def _named(link: Link | None) -> str | None:
    if link is None:
        return None
    return link.label


# test cases


def _descriptor() -> PageDescriptor:
    from wiki_api.core import PageDescriptor as Described

    return Described.model_validate(
        {
            "entity": {
                "type": "npc",
                "id": 50,
                "slug": "king-black-dragon",
                "label": "King Black Dragon",
            },
            "type": "npc",
            "description": "The biggest, meanest dragon around.",
            "data_version": "fixture-0001",
        }
    )


def _block(total: int = 2) -> Block:
    from wiki_api.core import Block as Reached

    return Reached.model_validate(
        {
            "walk": {
                "origin": {"type": "npc", "id": 50},
                "rel": "drops",
                "direction": "forward",
            },
            "label": "Drops",
            "group": "drops",
            "order": 10,
            "rows": {
                "items": [
                    {
                        "link": {
                            "type": "item",
                            "id": 536,
                            "slug": "dragon-bones",
                            "label": "Dragon bones",
                        },
                        "type": "item",
                        "attributes": [
                            {
                                "key": "chance",
                                "value": 1 / 128,
                                "label": "Chance",
                                "group": "rate",
                                "order": 5,
                                "format": "rate",
                                "prominent": True,
                            },
                            {
                                "key": "denominator",
                                "value": 128.0,
                                "label": "Out of",
                                "group": "rate",
                                "order": 20,
                                "format": "float",
                            },
                        ],
                    }
                ],
                "total": total,
                "limit": 10,
                "offset": 0,
            },
            "suppressed": 1,
        }
    )


def test_a_thing_carries_who_it_is_without_carrying_a_page() -> None:
    thing = thing_of(_descriptor())
    assert thing.name == "King Black Dragon"
    assert thing.id == 50
    assert thing.summary is not None
    assert thing.reachable == ()


def test_a_way_onwards_says_how_much_there_is_and_what_to_call() -> None:
    descriptor = _descriptor().model_copy(update={"blocks": (_block(total=1286),)})
    onwards = thing_of(descriptor).reachable[0]
    assert onwards.total == 1286
    assert onwards.tool == "drops"
    assert onwards.examples == ("Dragon bones",)


def test_a_way_onwards_shows_a_taste_and_never_the_whole_list() -> None:
    from wiki_api.core import Block as Reached

    block = _block()
    rows = block.rows.model_copy(
        update={"items": block.rows.items * (MOST_EXAMPLES + 2), "total": 5}
    )
    crowded: Reached = block.model_copy(update={"rows": rows})
    descriptor = _descriptor().model_copy(update={"blocks": (crowded,)})
    assert len(thing_of(descriptor).reachable[0].examples) == MOST_EXAMPLES


def test_a_neighbour_keeps_only_what_the_registry_marks_worth_keeping() -> None:
    neighbour = related_of(_block(), of="King Black Dragon").neighbours[0]
    assert neighbour.facts == {"Chance": "1/128"}
    assert neighbour.name == "Dragon bones"


def test_a_page_says_what_to_pass_back_to_read_the_rest() -> None:
    related = related_of(_block(total=50), of="King Black Dragon")
    assert related.next_offset == 1
    assert related.total == 50


def test_the_last_page_asks_for_nothing_further() -> None:
    related = related_of(_block(total=1), of="King Black Dragon")
    assert related.next_offset is None


def test_a_row_that_could_not_be_shown_is_counted_rather_than_hidden() -> None:
    assert related_of(_block(), of="King Black Dragon").left_out == 1


def test_a_variant_says_which_thing_it_is_really_a_form_of() -> None:
    from wiki_api.domain.identity import Link as Pointer

    canonical = Pointer(
        type=EntityType.ITEM,
        id=4587,
        slug="dragon-scimitar",
        label="Dragon scimitar",
    )
    descriptor = _descriptor().model_copy(update={"canonical": canonical})
    assert thing_of(descriptor).same_thing_as == "Dragon scimitar"


def test_a_thing_that_is_its_own_self_says_nothing_about_another() -> None:
    assert thing_of(_descriptor()).same_thing_as is None


def test_a_listing_carries_names_and_what_to_ask_for_next() -> None:
    from wiki_api.core import EntitySummary as Listed
    from wiki_api.domain.page import Page as Listing

    page = Listing[Listed](
        items=(
            Listed.model_validate(
                {
                    "link": {
                        "type": "item",
                        "id": 4587,
                        "slug": "dragon-scimitar",
                        "label": "Dragon scimitar",
                    },
                    "type": "item",
                    "description": "A vicious, curved sword.",
                }
            ),
        ),
        total=40,
        limit=1,
        offset=0,
    )
    matches = matches_of(page, "fixture-0001")
    assert matches.found[0].name == "Dragon scimitar"
    assert matches.found[0].summary is not None
    assert matches.next_offset == 1
    assert matches.total == 40


def test_a_projection_is_far_smaller_than_the_page_it_came_from() -> None:
    descriptor = _descriptor().model_copy(update={"blocks": (_block(),)})
    assert len(thing_of(descriptor).model_dump_json()) < len(
        descriptor.model_dump_json()
    )
