"""Shrink the core's answers for a reader that pays per word.

Each carries what the question needs, a count of what was left out, and the call that
would fetch it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from wiki_api.core import prominent_values
from wiki_api.domain.attributes import ATTRIBUTE_SPECS
from wiki_api.domain.identity import EntityType
from wiki_api.domain.relationships import RELATIONSHIP_SPECS
from wiki_api.surfaces.mcp.naming import tool_name
from wiki_api.surfaces.mcp.values import labelled

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pydantic import GetJsonSchemaHandler, SerializerFunctionWrapHandler
    from pydantic.json_schema import JsonSchemaValue
    from pydantic_core import CoreSchema

    from wiki_api.core import (
        AttributeValue,
        Block,
        Compared,
        EntitySummary,
        PageDescriptor,
        Row,
        SearchResult,
        TypeInfo,
    )
    from wiki_api.domain.attributes import AttributeSpec
    from wiki_api.domain.identity import Link
    from wiki_api.domain.page import Page
    from wiki_api.domain.prices import PriceMovement

MOST_EXAMPLES: Final = 3
DEFINITIONS: Final = "$defs"
POINTER: Final = "$ref"
DEFINITION_PREFIX: Final = "#/$defs/"
UP: Final = "up"
DOWN: Final = "down"
NOWHERE: Final = "nowhere"


def inlined(schema: JsonSchemaValue) -> JsonSchemaValue:
    """Fold a schema's definitions into the places that point at them, so it stands on
    its own wherever it is quoted.
    """
    held: Mapping[str, JsonSchemaValue] = schema.get(DEFINITIONS, {})
    standalone = {key: value for key, value in schema.items() if key != DEFINITIONS}
    folded: JsonSchemaValue = _resolved(standalone, held)
    return folded


def _resolved(node: object, held: Mapping[str, JsonSchemaValue]) -> Any:
    if isinstance(node, dict):
        pointed = node.get(POINTER)
        if isinstance(pointed, str) and pointed.startswith(DEFINITION_PREFIX):
            return _resolved(held[pointed.removeprefix(DEFINITION_PREFIX)], held)
        return {key: _resolved(value, held) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolved(value, held) for value in node]
    return node


def says_nothing(value: object) -> bool:
    """Say whether a field carries no answer, so writing it down would cost a reader
    without telling them anything.
    """
    if isinstance(value, str):
        return False
    return value is None or (isinstance(value, list | tuple | dict | set) and not value)


class Compact(BaseModel):
    """Write only the fields that carry an answer, because a reader is charged for
    every field either way.
    """

    model_config = ConfigDict(frozen=True)

    @model_serializer(mode="wrap")
    def _kept(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        written: dict[str, Any] = handler(self)
        return {key: value for key, value in written.items() if not says_nothing(value)}

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        if handler.mode == "serialization":
            return inlined(cls.model_json_schema(mode="validation"))
        declared: JsonSchemaValue = handler(core_schema)
        return declared


REF_NOTE: Final = (
    "how to name this exact one back to a tool. It addresses the game, it is not "
    "something a person asked for: never write it into an answer"
)


def ref_of(link: Link) -> str:
    """The handle a tool takes to reach exactly this one thing and no namesake."""
    return str(link.key)


class Addressed(Compact):
    """What a thing is called, and the handle that reaches this exact one.

    `ref` is for calling the next tool with; it is never part of an answer. Anything
    that sets one namesake apart from another belongs in `facts`, where it can be put
    to a person in words they recognise.
    """

    name: str
    type: EntityType
    ref: str = Field(description=REF_NOTE)


class Neighbour(Addressed):
    """One thing an answer names, and the values that came with it."""

    facts: dict[str, str] = Field(default_factory=dict)


class Reachable(Compact):
    """One way onwards from a thing: how much there is, and what to call for it."""

    tool: str
    label: str
    total: int = Field(ge=0)
    examples: tuple[str, ...] = ()


class Thing(Addressed):
    """One thing, its values worth knowing, and every way onwards from it as a count
    rather than contents.
    """

    summary: str | None = None
    facts: dict[str, str] = Field(default_factory=dict)
    same_thing_as: str | None = None
    others_with_this_name: int = Field(default=0, ge=0)
    reachable: tuple[Reachable, ...] = ()


class Related(Compact):
    """One page of one way onwards, and what to pass back to read the next."""

    of: str
    label: str
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    neighbours: tuple[Neighbour, ...] = ()
    next_offset: int | None = None
    left_out: int = Field(default=0, ge=0)


class Candidate(Addressed):
    """One thing a set of words turned up, named well enough to ask about."""

    summary: str | None = None


class Matches(Compact):
    """Whatever a question turned up, and what to pass back for the rest."""

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    found: tuple[Candidate, ...] = ()
    next_offset: int | None = None
    data_version: str


class Sort(Compact):
    """One sort of thing this build knows about, and how many of them there are."""

    type: EntityType
    label: str
    plural: str
    total: int = Field(ge=0)


class Sorts(Compact):
    """Every sort of thing that can be asked about."""

    sorts: tuple[Sort, ...] = ()
    data_version: str


class Ranking(Compact):
    """One page of things a number picked out, and what to pass back for the rest."""

    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    found: tuple[Neighbour, ...] = ()
    next_offset: int | None = None


class Movement(Compact):
    """Which way one thing's worth went over a stretch of the record, and how far."""

    of: str
    went: str
    change: int
    share: str
    opened: int
    opened_on: str
    closed: int
    closed_on: str
    lowest: int
    highest: int
    readings: int = Field(ge=1)
    trust: str


def ranking_of(compared: Compared) -> Ranking:
    """Shrink one page of a comparison to the names and the numbers behind them."""
    return Ranking(
        total=compared.rows.total,
        offset=compared.rows.offset,
        found=tuple(_carried(row) for row in compared.rows.items),
        next_offset=compared.rows.next_offset,
    )


def movement_of(went: PriceMovement, of: str) -> Movement:
    """Shrink a stretch of the record to which way it went and by how much."""
    return Movement(
        of=of,
        went=_which_way(went.change),
        change=went.change,
        share=f"{went.share:+.1%}",
        opened=went.opened,
        opened_on=went.opened_on.isoformat(),
        closed=went.closed,
        closed_on=went.closed_on.isoformat(),
        lowest=went.low,
        highest=went.high,
        readings=went.entries,
        trust=went.confidence.value,
    )


def _which_way(change: int) -> str:
    if change > 0:
        return UP
    if change < 0:
        return DOWN
    return NOWHERE


def thing_of(descriptor: PageDescriptor, namesakes: int = 0) -> Thing:
    """Shrink a whole page to what a reader would use."""
    return Thing(
        name=descriptor.entity.label,
        type=descriptor.type,
        ref=ref_of(descriptor.entity),
        summary=descriptor.description,
        facts=labelled(_all_values(descriptor), ATTRIBUTE_SPECS[descriptor.type]),
        same_thing_as=_named(descriptor.canonical),
        others_with_this_name=namesakes,
        reachable=tuple(_reachable(block) for block in descriptor.blocks),
    )


def related_of(block: Block, of: str) -> Related:
    """Shrink one page of one way onwards."""
    declared = RELATIONSHIP_SPECS[block.walk.rel].edge_attributes
    return Related(
        of=of,
        label=block.label,
        total=block.rows.total,
        offset=block.rows.offset,
        neighbours=tuple(_neighbour(row, declared) for row in block.rows.items),
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
                ref=ref_of(summary.link),
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


def _neighbour(row: Row, declared: Sequence[AttributeSpec] = ()) -> Neighbour:
    """Write down what the link says and what the thing at the far end is known by,
    so a reader can rank a page of them without fetching each one.
    """
    return Neighbour(
        name=row.link.label,
        type=row.type,
        ref=ref_of(row.link),
        facts=labelled(prominent_values(row.attributes), declared)
        | labelled(row.about, ATTRIBUTE_SPECS[row.type]),
    )


def _carried(row: Row) -> Neighbour:
    """Keep every value a row carries, because a comparison asked for all of them."""
    return Neighbour(
        name=row.link.label,
        type=row.type,
        ref=ref_of(row.link),
        facts=labelled(row.attributes) | labelled(row.about, ATTRIBUTE_SPECS[row.type]),
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
    assert thing.ref == "npc:50"
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


def _recorded(entity_type: EntityType) -> PageDescriptor:
    from wiki_api.core import PageDescriptor as Described
    from wiki_api.core.values import declared_values

    specs = [spec for spec in ATTRIBUTE_SPECS[entity_type] if spec.display]
    values = declared_values(
        specs,
        {
            spec.key: {part.key: 1 for part in spec.fields} if spec.fields else 1
            for spec in specs
        },
    )
    return Described(
        entity=_link(entity_type),
        type=entity_type,
        infobox=values,
        data_version="fixture-0001",
    )


def _link(entity_type: EntityType) -> Link:
    from wiki_api.domain.identity import Link as Pointer

    return Pointer(type=entity_type, id=1, slug="recorded", label="Recorded")


def test_a_thing_writes_down_every_value_it_records() -> None:
    for entity_type in EntityType:
        descriptor = _recorded(entity_type)
        written = thing_of(descriptor).facts
        assert set(written) == {
            value.label for value in _all_values(descriptor) if not value.technical
        }


def test_a_value_a_reader_could_not_see_before_is_one_a_question_can_reach() -> None:
    """Everything but the few marked worth a hover used to be dropped, so a reader
    was told the wiki holds nothing it had not been shown.
    """
    descriptor = _recorded(EntityType.NPC)
    shown = thing_of(descriptor).facts
    hidden = [
        value.label
        for value in _all_values(descriptor)
        if not value.prominent and not value.technical
    ]
    assert hidden
    assert set(hidden) <= set(shown)


def test_a_thing_names_the_parts_of_a_value_that_declares_them() -> None:
    packed = next(spec for spec in ATTRIBUTE_SPECS[EntityType.ITEM] if spec.fields)
    written = thing_of(_recorded(EntityType.ITEM)).facts[packed.label]
    for part in packed.fields:
        assert part.label in written


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


def test_a_field_holding_nothing_is_recognised_as_saying_nothing() -> None:
    empty: tuple[object, ...] = (None, (), [], {}, set())
    for nothing in empty:
        assert says_nothing(nothing)


def test_a_number_or_a_word_always_says_something() -> None:
    filled: tuple[object, ...] = (0, 0.0, False, "", "no", (1,), {"a": 1})
    for something in filled:
        assert not says_nothing(something)


def test_a_field_with_nothing_in_it_is_never_written_down() -> None:
    written = thing_of(_descriptor()).model_dump()
    assert "same_thing_as" not in written
    assert "reachable" not in written
    assert "facts" not in written


def test_a_field_that_answers_survives_being_shrunk() -> None:
    written = thing_of(_descriptor()).model_dump()
    assert written["name"] == "King Black Dragon"
    assert written["ref"] == "npc:50"
    assert written["summary"]


def test_a_zero_is_an_answer_rather_than_a_blank() -> None:
    written = related_of(_block(total=1), of="King Black Dragon").model_dump()
    assert written["offset"] == 0
    assert "next_offset" not in written


def test_shrinking_changes_what_is_written_and_never_what_it_says() -> None:
    thing = thing_of(_descriptor().model_copy(update={"blocks": (_block(),)}))
    written = thing.model_dump()
    assert written == {
        key: value
        for key, value in thing.model_dump(warnings=False).items()
        if not says_nothing(value)
    }
    assert Thing.model_validate({**written, "reachable": []}).name == thing.name


def test_the_shape_a_reader_is_told_about_still_declares_every_field() -> None:
    declared = Thing.model_json_schema()["properties"]
    assert "same_thing_as" in declared
    assert "reachable" in declared


def test_the_shape_quoted_to_a_reader_stands_on_its_own() -> None:
    quoted = Thing.model_json_schema(mode="serialization")
    assert DEFINITIONS not in quoted
    assert POINTER not in json.dumps(quoted)
    assert quoted["properties"]["reachable"]["items"]["properties"]["tool"]


def test_the_shape_quoted_says_the_same_as_the_shape_declared() -> None:
    quoted = Thing.model_json_schema(mode="serialization")
    declared = Thing.model_json_schema(mode="validation")
    assert set(quoted["properties"]) == set(declared["properties"])
    assert quoted["required"] == declared["required"]


def test_a_definition_pointed_at_twice_is_folded_in_both_times() -> None:
    folded = inlined(
        {
            DEFINITIONS: {"Word": {"type": "string"}},
            "properties": {
                "one": {POINTER: f"{DEFINITION_PREFIX}Word"},
                "two": {"items": {POINTER: f"{DEFINITION_PREFIX}Word"}},
            },
        }
    )
    assert folded == {
        "properties": {
            "one": {"type": "string"},
            "two": {"items": {"type": "string"}},
        }
    }


def test_a_shrunk_answer_still_reads_back_as_the_shape_it_declares() -> None:
    thing = thing_of(_descriptor().model_copy(update={"blocks": (_block(),)}))
    assert Thing.model_validate(thing.model_dump()) == thing


def test_a_thing_is_addressed_by_a_handle_rather_than_a_bare_number() -> None:
    """A bare `id` read as a fact about the thing, and answers came back saying
    'NPC 8349' and 'Phoenix crossbow (item:767)'. A ref says what it is for.
    """
    thing = thing_of(_descriptor())
    assert thing.ref == "npc:50"
    assert "id" not in thing.model_dump()


def test_the_handle_a_ref_carries_is_one_a_tool_takes_back() -> None:
    from wiki_api.domain.identity import EntityKey

    thing = thing_of(_descriptor())
    assert EntityKey.parse(thing.ref) == EntityKey.parse("npc:50")


def test_every_addressed_shape_says_a_ref_is_not_for_answering_with() -> None:
    for shape in (Thing, Neighbour, Candidate):
        described = shape.model_json_schema()["properties"]["ref"]["description"]
        assert "never write it into an answer" in described
