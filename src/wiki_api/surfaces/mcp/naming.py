"""Name each way of following a link, from the registry rather than by hand, so one
declared later turns up on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from wiki_api.core import Direction
from wiki_api.domain.identity import EntityType
from wiki_api.domain.presentation import ENTITY_TYPE_META
from wiki_api.domain.relationships import RELATIONSHIP_SPECS

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.domain.relationships import RelationshipSpec, RelationshipType

SEPARATOR = re.compile(r"[^a-z0-9]+")
VOWELS = "aeiou"

SORTS_TOOL = "list_sorts"
CLOSE_NAMES_TOOL = "find_close_names"
WRITTEN_TOOLS = (
    "search",
    "get_thing",
    "list_things",
    "about",
    SORTS_TOOL,
    CLOSE_NAMES_TOOL,
)


@dataclass(frozen=True)
class Followed:
    """One way of following one link, as a tool a reader can call."""

    rel: RelationshipType
    direction: Direction
    name: str
    description: str
    asked: tuple[EntityType, ...]


def tool_name(spec: RelationshipSpec, direction: Direction) -> str:
    """Name the tool that follows this link this way round."""
    return SEPARATOR.sub("_", label_of(spec, direction).lower()).strip("_")


def label_of(spec: RelationshipSpec, direction: Direction) -> str:
    """Read the registry's own words for this link, this way round."""
    if direction is Direction.FORWARD:
        return spec.forward_label
    return spec.inverse_label


def asked_of(spec: RelationshipSpec, direction: Direction) -> tuple[EntityType, ...]:
    """List the sorts of thing a caller names to follow this link this way."""
    types = spec.src_types if direction is Direction.FORWARD else spec.dst_types
    return _ordered(types)


def answered_with(
    spec: RelationshipSpec, direction: Direction
) -> tuple[EntityType, ...]:
    """List the sorts of thing that come back."""
    types = spec.dst_types if direction is Direction.FORWARD else spec.src_types
    return _ordered(types)


def described(spec: RelationshipSpec, direction: Direction) -> str:
    """Write the words a model reads to decide whether this is the tool it wants."""
    label = label_of(spec, direction)
    asked = _words(asked_of(spec, direction))
    answered = _words(answered_with(spec, direction), plural=True)
    return (
        f'"{label}". Give the name of {_article(asked)} {asked} and this answers '
        f"with the {answered} it is joined to that way. The answer arrives one page "
        "at a time; to read further, call it again with the offset the last answer "
        "reported."
    )


def followable() -> tuple[Followed, ...]:
    """List every way of following every link the registry declares, in a stable
    order.
    """
    return tuple(
        Followed(
            rel=spec.rel,
            direction=direction,
            name=tool_name(spec, direction),
            description=described(spec, direction),
            asked=asked_of(spec, direction),
        )
        for spec in sorted(RELATIONSHIP_SPECS.values(), key=lambda spec: spec.order)
        for direction in Direction
    )


def _ordered(types: frozenset[EntityType]) -> tuple[EntityType, ...]:
    return tuple(
        entity_type for entity_type in _declared_order() if entity_type in types
    )


def _declared_order() -> tuple[EntityType, ...]:
    return tuple(
        entity_type
        for entity_type, _ in sorted(
            ENTITY_TYPE_META.items(), key=lambda entry: entry[1].order
        )
    )


def _words(types: Sequence[EntityType], *, plural: bool = False) -> str:
    said = [
        ENTITY_TYPE_META[entity_type].plural.lower()
        if plural
        else ENTITY_TYPE_META[entity_type].label.lower()
        for entity_type in types
    ]
    if len(said) == 1:
        return said[0]
    return f"{', '.join(said[:-1])} or {said[-1]}"


def _article(said: str) -> str:
    if said[:1] in VOWELS:
        return "an"
    return "a"


# test cases


def _spec(rel_value: str) -> RelationshipSpec:
    from wiki_api.domain.relationships import RelationshipType as Rel

    return RELATIONSHIP_SPECS[Rel(rel_value)]


def test_a_tool_is_named_with_the_registry_own_words() -> None:
    spec = _spec("sells")
    assert tool_name(spec, Direction.FORWARD) == SEPARATOR.sub(
        "_", spec.forward_label.lower()
    )
    assert tool_name(spec, Direction.REVERSE) == SEPARATOR.sub(
        "_", spec.inverse_label.lower()
    )


def test_a_tool_name_is_always_usable_as_an_identifier() -> None:
    for followed in followable():
        assert followed.name.isidentifier()
        assert followed.name.islower()


def test_every_way_of_following_every_link_is_offered() -> None:
    assert len(followable()) == len(RELATIONSHIP_SPECS) * len(Direction)


def test_no_two_ways_of_following_a_link_share_a_name() -> None:
    names = [followed.name for followed in followable()]
    assert len(set(names)) == len(names)


def test_the_order_they_are_offered_in_never_wanders() -> None:
    assert [followed.name for followed in followable()] == [
        followed.name for followed in followable()
    ]


def test_the_two_directions_ask_for_opposite_ends() -> None:
    spec = _spec("sells")
    assert asked_of(spec, Direction.FORWARD) == answered_with(spec, Direction.REVERSE)
    assert answered_with(spec, Direction.FORWARD) == asked_of(spec, Direction.REVERSE)


def test_a_description_says_what_to_give_and_what_comes_back() -> None:
    for followed in followable():
        assert followed.description
        assert "offset" in followed.description


def test_no_two_descriptions_read_the_same() -> None:
    described_as = [followed.description for followed in followable()]
    assert len(set(described_as)) == len(described_as)


def test_several_sorts_of_thing_are_said_as_a_reader_would_say_them() -> None:
    assert _words((EntityType.ITEM,)) == "item"
    assert _words((EntityType.ITEM, EntityType.NPC)) == "item or npc"
    assert _words((EntityType.ITEM, EntityType.NPC, EntityType.SHOP)) == (
        "item, npc or shop"
    )


def test_the_tools_written_by_hand_never_collide_with_the_generated_ones() -> None:
    assert not set(WRITTEN_TOOLS) & {followed.name for followed in followable()}


def test_every_tool_written_by_hand_is_named_once() -> None:
    assert len(set(WRITTEN_TOOLS)) == len(WRITTEN_TOOLS)


def test_the_tools_a_reader_is_pointed_at_are_tools_that_exist() -> None:
    assert {SORTS_TOOL, CLOSE_NAMES_TOOL} <= set(WRITTEN_TOOLS)


def test_a_word_beginning_with_a_vowel_gets_the_other_article() -> None:
    assert _article("item") == "an"
    assert _article("shop") == "a"
