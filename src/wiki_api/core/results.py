"""What the query core hands back, in shapes no surface has to reinterpret.

Every value carries the presentation facts the registry declares for it.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wiki_api.domain.attributes import AttributeFormat, AttributeSpec
from wiki_api.domain.entity import Entity
from wiki_api.domain.identity import EntityKey, EntityType, Link
from wiki_api.domain.page import Page
from wiki_api.domain.presentation import GroupPlacement
from wiki_api.domain.relationships import RelationshipSpec, RelationshipType
from wiki_api.domain.vocabulary import (
    AttributeGroup,
    GameEnum,
    HiddenReason,
    RelationshipGroup,
    Unit,
)


class Direction(GameEnum):
    """Which way a relationship was read: out of the entity, or back into it."""

    FORWARD = "forward"
    REVERSE = "reverse"

    @property
    def opposite(self) -> Direction:
        if self is Direction.FORWARD:
            return Direction.REVERSE
        return Direction.FORWARD


class AttributeValue(BaseModel):
    """One field of an entity, carrying the label, group, order, format and unit needed
    to display it without recognising `key`.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    value: JsonValue
    label: str
    group: AttributeGroup
    order: int
    format: AttributeFormat
    unit: Unit | None = None
    derived: bool = False
    prominent: bool = False
    choices: tuple[str, ...] | None = None

    @classmethod
    def of(cls, spec: AttributeSpec, value: JsonValue) -> AttributeValue:
        return cls(
            key=spec.key,
            value=value,
            label=spec.label,
            group=spec.group,
            order=spec.order,
            format=spec.format,
            unit=spec.unit,
            derived=spec.derived,
            prominent=spec.prominent,
            choices=spec.choices,
        )


ATTRIBUTE_SECTION: Final = "attributes"


class Section(BaseModel):
    """A group of attributes drawn as one block of the page body, with a `render` word
    saying how it wants to be laid out.
    """

    model_config = ConfigDict(frozen=True)

    render: str = ATTRIBUTE_SECTION
    group: AttributeGroup
    label: str
    placement: GroupPlacement
    order: int
    attributes: tuple[AttributeValue, ...]


class Row(BaseModel):
    """One entity reached over a relationship, plus what the link itself records."""

    model_config = ConfigDict(frozen=True)

    link: Link
    type: EntityType
    attributes: tuple[AttributeValue, ...]


class Walk(BaseModel):
    """The question a block answers: which entity, which relationship, which way."""

    model_config = ConfigDict(frozen=True)

    origin: EntityKey
    rel: RelationshipType
    direction: Direction


class Block(BaseModel):
    """One relationship's worth of a page: a label, a first page of rows, the walk that
    produced them, and a count of rows left out because their target is unpublished.
    """

    model_config = ConfigDict(frozen=True)

    walk: Walk
    label: str
    group: RelationshipGroup
    order: int
    rows: Page[Row]
    suppressed: int = Field(default=0, ge=0)

    @property
    def is_empty(self) -> bool:
        return self.rows.total == 0


class PageDescriptor(BaseModel):
    """A whole entity page described as data: identity, a line of description, the
    infobox, the attribute sections, and a first page of every set of related entities.
    """

    model_config = ConfigDict(frozen=True)

    entity: Link
    type: EntityType
    description: str | None = None
    canonical: Link | None = None
    variants: tuple[Link, ...] = ()
    infobox: tuple[AttributeValue, ...] = ()
    sections: tuple[Section, ...] = ()
    blocks: tuple[Block, ...] = ()
    data_version: str


class Tooltip(BaseModel):
    """The short form of an entity: identity, one line of description, and the few
    values the registry marks as worth showing.
    """

    model_config = ConfigDict(frozen=True)

    link: Link
    type: EntityType
    description: str | None = None
    attributes: tuple[AttributeValue, ...] = ()


class EntitySummary(BaseModel):
    """One entity as it appears in a list: where it points, and a line about it."""

    model_config = ConfigDict(frozen=True)

    link: Link
    type: EntityType
    description: str | None = None


class SearchResult(EntitySummary):
    """One entity a search matched, with its score. A higher score matched better."""

    score: float = Field(ge=0.0)


class Match(BaseModel):
    """The single entity a name most likely meant, or null when nothing matched,
    together with the ranked candidates either way.
    """

    model_config = ConfigDict(frozen=True)

    best_match: Link | None = None
    results: Page[SearchResult]


class TypeInfo(BaseModel):
    """One entity type, with every attribute and relationship declared for it."""

    model_config = ConfigDict(frozen=True)

    type: EntityType
    label: str
    plural: str
    order: int
    attributes: tuple[AttributeSpec, ...]
    relationships: tuple[RelationshipSpec, ...]


class Found[T](BaseModel):
    """The lookup succeeded, and `value` holds what it found."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["found"] = "found"
    value: T


class Moved(BaseModel):
    """The reference is retired. The entity answers at `target` now."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["moved"] = "moved"
    target: Link


class Hidden(BaseModel):
    """The entity exists in this build but is deliberately not served."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["hidden"] = "hidden"
    key: EntityKey
    reason: HiddenReason | None = None


class Missing(BaseModel):
    """Nothing in this build answers to that reference."""

    model_config = ConfigDict(frozen=True)

    outcome: Literal["missing"] = "missing"
    reference: str


Absent = Moved | Hidden | Missing
EntityResolution = Found[Entity] | Absent
PageResolution = Found[PageDescriptor] | Absent
TooltipResolution = Found[Tooltip] | Absent
BlockResolution = Found[Block] | Absent


class Named[T](BaseModel):
    """What a name turned out to mean, which entity it was answered about, and what else
    the words matched.
    """

    model_config = ConfigDict(frozen=True)

    resolution: Found[T] | Absent
    subject: Link | None = None
    alternatives: tuple[Link, ...] = ()


# test cases


def _link() -> Link:
    return Link(
        type=EntityType.ITEM, id=4587, slug="dragon-scimitar", label="Dragon scimitar"
    )


def test_a_direction_knows_its_opposite() -> None:
    assert Direction.FORWARD.opposite is Direction.REVERSE
    assert Direction.REVERSE.opposite is Direction.FORWARD


def test_a_value_carries_the_registry_facts_that_render_it() -> None:
    spec = AttributeSpec(
        key="shop_price",
        label="Shop price",
        group=AttributeGroup.TRADE,
        order=30,
        format=AttributeFormat.GP,
        prominent=True,
    )
    value = AttributeValue.of(spec, 100)
    assert value.value == 100
    assert value.label == "Shop price"
    assert value.format is AttributeFormat.GP
    assert value.prominent is True


def test_a_block_carries_the_walk_that_would_fetch_its_next_page() -> None:
    origin = EntityKey(type=EntityType.ITEM, id=4587)
    block = Block(
        walk=Walk(
            origin=origin,
            rel=RelationshipType.DROPS,
            direction=Direction.REVERSE,
        ),
        label="Dropped by",
        group=RelationshipGroup.DROPS,
        order=10,
        rows=Page[Row](items=(), total=1286, limit=10, offset=0),
    )
    assert block.walk.origin == origin
    assert block.rows.total == 1286
    assert block.is_empty is False


def test_a_block_with_nothing_in_it_says_so() -> None:
    block = Block(
        walk=Walk(
            origin=EntityKey(type=EntityType.ITEM, id=995),
            rel=RelationshipType.SELLS,
            direction=Direction.REVERSE,
        ),
        label="Sold in",
        group=RelationshipGroup.TRADE,
        order=20,
        rows=Page[Row](items=(), total=0, limit=10, offset=0),
    )
    assert block.is_empty is True


def test_every_outcome_names_itself_for_a_reader() -> None:
    key = EntityKey(type=EntityType.NPC, id=3089)
    assert Found[int](value=1).outcome == "found"
    assert Moved(target=_link()).outcome == "moved"
    assert Hidden(key=key).outcome == "hidden"
    assert Missing(reference="item:1").outcome == "missing"


def test_a_search_result_is_a_summary_that_also_scored() -> None:
    result = SearchResult(link=_link(), type=EntityType.ITEM, score=12.5)
    assert isinstance(result, EntitySummary)
    assert result.score == 12.5


def test_a_section_says_how_it_wants_to_be_laid_out() -> None:
    section = Section(
        group=AttributeGroup.EQUIPMENT,
        label="Equipment",
        placement=GroupPlacement.SECTION,
        order=50,
        attributes=(),
    )
    assert section.render == ATTRIBUTE_SECTION


def test_a_section_can_be_laid_out_some_other_way_without_a_model_change() -> None:
    section = Section(
        render="price_series",
        group=AttributeGroup.TRADE,
        label="Price",
        placement=GroupPlacement.SECTION,
        order=60,
        attributes=(),
    )
    assert section.render == "price_series"


def test_a_name_that_meant_something_carries_what_it_meant() -> None:
    named = Named[int](resolution=Found[int](value=7))
    assert isinstance(named.resolution, Found)
    assert named.resolution.value == 7
    assert named.alternatives == ()


def test_a_name_that_meant_nothing_still_offers_what_was_close() -> None:
    named = Named[int](
        resolution=Missing(reference="dragon scimtar"), alternatives=(_link(),)
    )
    assert isinstance(named.resolution, Missing)
    assert named.alternatives[0].label == "Dragon scimitar"


def test_results_are_immutable() -> None:
    import pytest

    summary = EntitySummary(link=_link(), type=EntityType.ITEM)
    frozen_field = "description"
    with pytest.raises(ValueError):
        setattr(summary, frozen_field, "something else")
