"""Answer a name that meant nothing, or meant something else.

On this surface an absence is part of the answer, never a raised error.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.core import Found, Hidden, Missing, Moved
from wiki_api.domain.identity import EntityType
from wiki_api.surfaces.mcp.naming import CLOSE_NAMES_TOOL, SORTS_TOOL
from wiki_api.surfaces.mcp.projection import Related, Thing, related_of, thing_of

if TYPE_CHECKING:
    from wiki_api.core import Absent, Block, Named, PageDescriptor
    from wiki_api.domain.identity import Link

MOST_OTHERS: Final = 5

RENAMED_NOTE = "that name is retired; ask again using the one below"
WITHHELD_NOTE = "that is in this build but is not published"
UNKNOWN_NOTE = (
    "nothing here answers to that name. It may be misspelt: settle with whoever "
    f"asked which sort of thing was meant, using `{SORTS_TOOL}` if that is unclear, "
    f"then call `{CLOSE_NAMES_TOOL}` for the real names closest to it. Put those "
    "names to whoever asked and use the one they choose; do not choose for them"
)
UNKNOWN_WITH_OTHERS = f"{UNKNOWN_NOTE}. One of the names below may be the one meant"


class Outcome(StrEnum):
    """How an answer turned out."""

    FOUND = "found"
    RENAMED = "renamed"
    WITHHELD = "withheld"
    UNKNOWN = "unknown"


class Suggestion(BaseModel):
    """One other name worth trying, with the identity behind it."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: EntityType
    id: int = Field(ge=0)


class Answer[T](BaseModel):
    """An answer, or the reason there isn't one.

    `note` says what went wrong; `others` offers names worth trying instead.
    """

    model_config = ConfigDict(frozen=True)

    outcome: Outcome
    result: T | None = None
    note: str | None = None
    others: tuple[Suggestion, ...] = ()
    data_version: str


def suggested(links: tuple[Link, ...]) -> tuple[Suggestion, ...]:
    """Pick the few other names worth putting in front of a reader."""
    return tuple(
        Suggestion(name=link.label, type=link.type, id=link.id)
        for link in links[:MOST_OTHERS]
    )


def refusal(absent: Absent) -> tuple[Outcome, str, tuple[Suggestion, ...]]:
    """Say why there is no answer, in terms a reader can act on."""
    if isinstance(absent, Moved):
        return Outcome.RENAMED, RENAMED_NOTE, suggested((absent.target,))
    if isinstance(absent, Hidden):
        return Outcome.WITHHELD, WITHHELD_NOTE, ()
    return Outcome.UNKNOWN, UNKNOWN_NOTE, ()


def about_thing(named: Named[PageDescriptor], data_version: str) -> Answer[Thing]:
    """Answer with one thing, or with why that name did not reach one."""
    if isinstance(named.resolution, Found):
        return Answer[Thing](
            outcome=Outcome.FOUND,
            result=thing_of(named.resolution.value),
            others=suggested(named.alternatives),
            data_version=data_version,
        )
    return _refused(named.resolution, named.alternatives, data_version)


def about_related(named: Named[Block], data_version: str) -> Answer[Related]:
    """Answer with one page of one way onwards, or why that name did not reach one."""
    if isinstance(named.resolution, Found) and named.subject is not None:
        return Answer[Related](
            outcome=Outcome.FOUND,
            result=related_of(named.resolution.value, of=named.subject.label),
            others=suggested(named.alternatives),
            data_version=data_version,
        )
    if isinstance(named.resolution, Found):
        return Answer[Related](
            outcome=Outcome.UNKNOWN,
            note=UNKNOWN_NOTE,
            data_version=data_version,
        )
    return _refused_related(named.resolution, named.alternatives, data_version)


def _refused(
    absent: Absent, alternatives: tuple[Link, ...], data_version: str
) -> Answer[Thing]:
    outcome, note, offered = refusal(absent)
    return Answer[Thing](
        outcome=outcome,
        note=_noted(outcome, note, alternatives),
        others=offered or suggested(alternatives),
        data_version=data_version,
    )


def _refused_related(
    absent: Absent, alternatives: tuple[Link, ...], data_version: str
) -> Answer[Related]:
    outcome, note, offered = refusal(absent)
    return Answer[Related](
        outcome=outcome,
        note=_noted(outcome, note, alternatives),
        others=offered or suggested(alternatives),
        data_version=data_version,
    )


def _noted(outcome: Outcome, note: str, alternatives: tuple[Link, ...]) -> str:
    if outcome is Outcome.UNKNOWN and alternatives:
        return UNKNOWN_WITH_OTHERS
    return note


# test cases


def _link(label: str = "Dragon scimitar", entity_id: int = 4587) -> Link:
    from wiki_api.domain.identity import EntityType as Type
    from wiki_api.domain.identity import Link as Pointer

    return Pointer(type=Type.ITEM, id=entity_id, slug="dragon-scimitar", label=label)


def _named_page() -> Named[PageDescriptor]:
    from wiki_api.core import Named as Meant
    from wiki_api.core import PageDescriptor as Described

    described = Described.model_validate(
        {
            "entity": {
                "type": "item",
                "id": 4587,
                "slug": "dragon-scimitar",
                "label": "Dragon scimitar",
            },
            "type": "item",
            "data_version": "fixture-0001",
        }
    )
    return Meant[Described](resolution=Found(value=described), subject=described.entity)


def test_an_answer_that_worked_carries_the_thing_and_nothing_else() -> None:
    answer = about_thing(_named_page(), "fixture-0001")
    assert answer.outcome is Outcome.FOUND
    assert answer.result is not None
    assert answer.result.name == "Dragon scimitar"
    assert answer.note is None


def test_a_retired_name_is_answered_with_the_one_that_replaced_it() -> None:
    outcome, note, offered = refusal(Moved(target=_link()))
    assert outcome is Outcome.RENAMED
    assert note == RENAMED_NOTE
    assert offered[0].name == "Dragon scimitar"


def test_something_withheld_says_so_without_saying_which_id() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    outcome, note, offered = refusal(
        Hidden(key=EntityKey(type=EntityType.NPC, id=3089))
    )
    assert outcome is Outcome.WITHHELD
    assert "3089" not in note
    assert offered == ()


def test_a_name_that_meant_nothing_says_so() -> None:
    outcome, note, _ = refusal(Missing(reference="dragon scimtar"))
    assert outcome is Outcome.UNKNOWN
    assert note == UNKNOWN_NOTE


def test_a_near_miss_points_at_what_was_close() -> None:
    from wiki_api.core import Named as Meant
    from wiki_api.core import PageDescriptor as Described

    named = Meant[Described](
        resolution=Missing(reference="dragon scimtar"), alternatives=(_link(),)
    )
    answer = about_thing(named, "fixture-0001")
    assert answer.outcome is Outcome.UNKNOWN
    assert answer.note == UNKNOWN_WITH_OTHERS
    assert answer.others[0].id == 4587


def test_a_thing_that_moved_is_answered_with_where_it_moved_to() -> None:
    from wiki_api.core import Named as Meant
    from wiki_api.core import PageDescriptor as Described

    named = Meant[Described](resolution=Moved(target=_link()))
    answer = about_thing(named, "fixture-0001")
    assert answer.outcome is Outcome.RENAMED
    assert answer.note == RENAMED_NOTE
    assert answer.others[0].name == "Dragon scimitar"


def test_a_walk_that_moved_is_answered_the_same_way_a_thing_is() -> None:
    from wiki_api.core import Block as Reached
    from wiki_api.core import Named as Meant

    named = Meant[Reached](resolution=Moved(target=_link()))
    answer = about_related(named, "fixture-0001")
    assert answer.outcome is Outcome.RENAMED
    assert answer.result is None


def test_a_walk_that_reached_nothing_says_so_rather_than_half_answering() -> None:
    from wiki_api.core import Block as Reached
    from wiki_api.core import Named as Meant

    named = Meant[Reached](resolution=Missing(reference="nothing"))
    assert about_related(named, "fixture-0001").outcome is Outcome.UNKNOWN


def test_a_walk_with_nothing_to_attribute_it_to_is_refused_rather_than_guessed() -> (
    None
):
    from wiki_api.core import Block as Reached
    from wiki_api.core import Found as Reached_
    from wiki_api.core import Named as Meant

    block = Reached.model_validate(
        {
            "walk": {
                "origin": {"type": "npc", "id": 50},
                "rel": "drops",
                "direction": "forward",
            },
            "label": "Drops",
            "group": "drops",
            "order": 10,
            "rows": {"items": [], "total": 0, "limit": 10, "offset": 0},
        }
    )
    named = Meant[Reached](resolution=Reached_(value=block), subject=None)
    answer = about_related(named, "fixture-0001")
    assert answer.outcome is Outcome.UNKNOWN
    assert answer.result is None


def test_only_a_few_other_names_are_ever_offered() -> None:
    many = tuple(_link(f"Candidate {number}", number) for number in range(20))
    assert len(suggested(many)) == MOST_OTHERS


def test_every_answer_says_which_build_it_came_from() -> None:
    from wiki_api.core import Named as Meant
    from wiki_api.core import PageDescriptor as Described

    refused = about_thing(
        Meant[Described](resolution=Missing(reference="nothing")), "fixture-0002"
    )
    assert refused.data_version == "fixture-0002"
    assert about_thing(_named_page(), "fixture-0001").data_version == "fixture-0001"


def test_an_outcome_is_a_word_a_reader_can_branch_on() -> None:
    assert {outcome.value for outcome in Outcome} == {
        "found",
        "renamed",
        "withheld",
        "unknown",
    }
