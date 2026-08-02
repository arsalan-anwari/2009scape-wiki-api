"""The typed links between entities, and the data each link carries."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from wiki_api.domain.attributes import (
    AttributeFormat,
    AttributeMeta,
    AttributeSpec,
    specs_of,
)
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.provenance import Provenance
from wiki_api.domain.space import Coordinate, SpawnKind
from wiki_api.domain.vocabulary import (
    COINS,
    AttributeGroup,
    GameEnum,
    RelationshipGroup,
    Unit,
    coerce_item_ref,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class RelationshipType(StrEnum):
    """The types of link one entity can have to another."""

    DROPS = "drops"
    SELLS = "sells"
    STAFFED_BY = "staffed_by"
    REWARDS = "rewards"
    USES_AMMUNITION = "uses_ammunition"
    LOCATED_IN = "located_in"
    PART_OF = "part_of"


class DropTableKind(GameEnum):
    """Which table inside a drop list a roll came from."""

    DEFAULT = "default"
    MAIN = "main"
    CHARM = "charm"
    TERTIARY = "tertiary"


class DropEdgeAttributes(BaseModel):
    """What an npc dropping an item is worth, keeping weight and denominator so a rate
    renders exactly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    weight: Annotated[
        float,
        AttributeMeta("Weight", AttributeGroup.RATE, 10, AttributeFormat.FLOAT),
    ] = Field(gt=0.0)
    denominator: Annotated[
        float,
        AttributeMeta("Out of", AttributeGroup.RATE, 20, AttributeFormat.FLOAT),
    ] = Field(gt=0.0)
    table_kind: Annotated[
        DropTableKind,
        BeforeValidator(DropTableKind.coerce),
        AttributeMeta("Drop table", AttributeGroup.RATE, 30, AttributeFormat.ENUM),
    ] = DropTableKind.MAIN
    min_amount: Annotated[
        int,
        AttributeMeta("Minimum amount", AttributeGroup.AMOUNT, 40, AttributeFormat.INT),
    ] = Field(default=1, ge=1)
    max_amount: Annotated[
        int,
        AttributeMeta("Maximum amount", AttributeGroup.AMOUNT, 50, AttributeFormat.INT),
    ] = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.max_amount < self.min_amount:
            raise ValueError("max_amount must not be below min_amount")
        if self.weight > self.denominator:
            raise ValueError("weight must not exceed the denominator")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def chance(
        self,
    ) -> Annotated[
        float,
        AttributeMeta(
            "Chance",
            AttributeGroup.RATE,
            5,
            AttributeFormat.RATE,
            derived=True,
            prominent=True,
        ),
    ]:
        """How likely one roll is, declared so a reader never divides two numbers."""
        return self.rate

    @property
    def rate(self) -> float:
        return self.weight / self.denominator

    @property
    def one_in(self) -> float:
        return self.denominator / self.weight


class SellEdgeAttributes(BaseModel):
    """What a shop asks for one line of its stock."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stock_amount: Annotated[
        int,
        AttributeMeta(
            "Stock", AttributeGroup.SHOP, 10, AttributeFormat.INT, prominent=True
        ),
    ] = Field(ge=0)
    restock_rate: Annotated[
        int,
        AttributeMeta("Restock rate", AttributeGroup.SHOP, 20, AttributeFormat.INT),
    ] = Field(default=100, ge=0)
    price: Annotated[
        int | None,
        AttributeMeta(
            "Price", AttributeGroup.SHOP, 30, AttributeFormat.GP, prominent=True
        ),
    ] = None
    currency: Annotated[
        EntityKey,
        BeforeValidator(coerce_item_ref),
        AttributeMeta("Currency", AttributeGroup.SHOP, 40, AttributeFormat.REF),
    ] = COINS
    slot: Annotated[
        int,
        AttributeMeta(
            "Slot", AttributeGroup.SHOP, 50, AttributeFormat.INT, display=False
        ),
    ] = Field(default=0, ge=0)


class StaffedByEdgeAttributes(BaseModel):
    """Nothing. Running a shop is the whole fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RewardEdgeAttributes(BaseModel):
    """How much of an item a quest hands over."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Annotated[
        int,
        AttributeMeta(
            "Amount", AttributeGroup.REWARD, 10, AttributeFormat.INT, prominent=True
        ),
    ] = Field(default=1, ge=1)


class AmmunitionEdgeAttributes(BaseModel):
    """Nothing. Taking the ammunition is the whole fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class LocatedInEdgeAttributes(BaseModel):
    """Where inside a place something stands, and why it is there."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: Annotated[
        Coordinate | None,
        AttributeMeta(
            "Position", AttributeGroup.MAP, 10, AttributeFormat.COORD, prominent=True
        ),
    ] = None
    spawn_kind: Annotated[
        SpawnKind,
        BeforeValidator(SpawnKind.coerce),
        AttributeMeta("Kind", AttributeGroup.MAP, 20, AttributeFormat.ENUM),
    ] = SpawnKind.NPC_SPAWN
    respawn_ticks: Annotated[
        int | None,
        AttributeMeta(
            "Respawn", AttributeGroup.MAP, 30, AttributeFormat.INT, unit=Unit.TICKS
        ),
    ] = None
    amount: Annotated[
        int,
        AttributeMeta("Amount", AttributeGroup.MAP, 40, AttributeFormat.INT),
    ] = Field(default=1, ge=1)


class PartOfEdgeAttributes(BaseModel):
    """Nothing. Sitting inside another place is the whole fact."""

    model_config = ConfigDict(frozen=True, extra="forbid")


EdgeAttributes = (
    DropEdgeAttributes
    | SellEdgeAttributes
    | StaffedByEdgeAttributes
    | RewardEdgeAttributes
    | AmmunitionEdgeAttributes
    | LocatedInEdgeAttributes
    | PartOfEdgeAttributes
)

EDGE_ATTRIBUTE_MODELS: Final[Mapping[RelationshipType, type[EdgeAttributes]]] = {
    RelationshipType.DROPS: DropEdgeAttributes,
    RelationshipType.SELLS: SellEdgeAttributes,
    RelationshipType.STAFFED_BY: StaffedByEdgeAttributes,
    RelationshipType.REWARDS: RewardEdgeAttributes,
    RelationshipType.USES_AMMUNITION: AmmunitionEdgeAttributes,
    RelationshipType.LOCATED_IN: LocatedInEdgeAttributes,
    RelationshipType.PART_OF: PartOfEdgeAttributes,
}


class RelationshipSpec(BaseModel):
    """One relationship as declared: a label each direction, the types it joins, and
    the attributes a link may carry.
    """

    model_config = ConfigDict(frozen=True)

    rel: RelationshipType
    forward_label: str
    inverse_label: str
    src_types: frozenset[EntityType]
    dst_types: frozenset[EntityType]
    edge_attributes: tuple[AttributeSpec, ...]
    group: RelationshipGroup
    order: int


def _spec(
    rel: RelationshipType,
    forward_label: str,
    inverse_label: str,
    src_types: frozenset[EntityType],
    dst_types: frozenset[EntityType],
    group: RelationshipGroup,
    order: int,
) -> RelationshipSpec:
    return RelationshipSpec(
        rel=rel,
        forward_label=forward_label,
        inverse_label=inverse_label,
        src_types=src_types,
        dst_types=dst_types,
        edge_attributes=specs_of(EDGE_ATTRIBUTE_MODELS[rel]),
        group=group,
        order=order,
    )


RELATIONSHIP_SPECS: Final[Mapping[RelationshipType, RelationshipSpec]] = {
    RelationshipType.DROPS: _spec(
        RelationshipType.DROPS,
        "Drops",
        "Dropped by",
        frozenset({EntityType.NPC}),
        frozenset({EntityType.ITEM}),
        RelationshipGroup.DROPS,
        10,
    ),
    RelationshipType.SELLS: _spec(
        RelationshipType.SELLS,
        "Sells",
        "Sold in",
        frozenset({EntityType.SHOP}),
        frozenset({EntityType.ITEM}),
        RelationshipGroup.TRADE,
        20,
    ),
    RelationshipType.STAFFED_BY: _spec(
        RelationshipType.STAFFED_BY,
        "Staffed by",
        "Runs shop",
        frozenset({EntityType.SHOP}),
        frozenset({EntityType.NPC}),
        RelationshipGroup.TRADE,
        30,
    ),
    RelationshipType.REWARDS: _spec(
        RelationshipType.REWARDS,
        "Rewards",
        "Reward from",
        frozenset({EntityType.QUEST}),
        frozenset({EntityType.ITEM}),
        RelationshipGroup.QUESTS,
        40,
    ),
    RelationshipType.USES_AMMUNITION: _spec(
        RelationshipType.USES_AMMUNITION,
        "Uses ammunition",
        "Used by",
        frozenset({EntityType.ITEM}),
        frozenset({EntityType.ITEM}),
        RelationshipGroup.EQUIPMENT,
        50,
    ),
    RelationshipType.LOCATED_IN: _spec(
        RelationshipType.LOCATED_IN,
        "Found in",
        "Found here",
        frozenset({EntityType.NPC, EntityType.SHOP, EntityType.ITEM, EntityType.QUEST}),
        frozenset({EntityType.LOCATION}),
        RelationshipGroup.MAP,
        60,
    ),
    RelationshipType.PART_OF: _spec(
        RelationshipType.PART_OF,
        "Part of",
        "Contains",
        frozenset({EntityType.LOCATION}),
        frozenset({EntityType.LOCATION}),
        RelationshipGroup.MAP,
        70,
    ),
}


def discriminator_of(attributes: EdgeAttributes) -> str:
    """Read what tells apart two edges joining the same pair, off the edge's own
    attributes.
    """
    if isinstance(attributes, LocatedInEdgeAttributes):
        return "" if attributes.at is None else str(attributes.at)
    if isinstance(attributes, DropEdgeAttributes):
        return attributes.table_kind.value
    return ""


class Edge(BaseModel):
    """One typed link between two entities."""

    model_config = ConfigDict(frozen=True)

    src: EntityKey
    rel: RelationshipType
    dst: EntityKey
    attributes: EdgeAttributes
    discriminator: str = ""
    order_key: int = 0
    provenance: Provenance

    @model_validator(mode="before")
    @classmethod
    def _coerce_attributes_and_key_the_edge(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        rel = data.get("rel")
        attributes = data.get("attributes")
        if rel is None or attributes is None:
            return data
        model = EDGE_ATTRIBUTE_MODELS[RelationshipType(rel)]
        if isinstance(attributes, dict):
            attributes = model.model_validate(attributes)
        if not isinstance(attributes, model):
            return data
        expected = discriminator_of(attributes)
        declared = data.get("discriminator")
        if declared is not None and declared != expected:
            raise ValueError(
                f"discriminator {declared!r} disagrees with the edge attributes, "
                f"which key this edge as {expected!r}"
            )
        return {**data, "attributes": attributes, "discriminator": expected}

    @model_validator(mode="after")
    def _check_against_the_registry(self) -> Self:
        spec = RELATIONSHIP_SPECS[self.rel]
        if self.src.type not in spec.src_types:
            raise ValueError(f"{self.rel.value} cannot start at {self.src.type.value}")
        if self.dst.type not in spec.dst_types:
            raise ValueError(f"{self.rel.value} cannot end at {self.dst.type.value}")
        expected = EDGE_ATTRIBUTE_MODELS[self.rel]
        if type(self.attributes) is not expected:
            raise ValueError(f"{self.rel.value} needs {expected.__name__}")
        if self.discriminator != discriminator_of(self.attributes):
            raise ValueError("an edge must be keyed by its own attributes")
        if self.rel is RelationshipType.PART_OF and self.src == self.dst:
            raise ValueError("a location cannot be part of itself")
        return self

    @property
    def spec(self) -> RelationshipSpec:
        return RELATIONSHIP_SPECS[self.rel]


# test cases


def _provenance() -> Provenance:
    return Provenance.model_validate({"source": "fixture", "game_version": "test"})


def test_every_relationship_type_is_registered_with_both_labels() -> None:
    for rel in RelationshipType:
        spec = RELATIONSHIP_SPECS[rel]
        assert spec.forward_label and spec.inverse_label
        assert spec.forward_label != spec.inverse_label
        assert rel in EDGE_ATTRIBUTE_MODELS
        assert isinstance(spec.group, RelationshipGroup)


def test_edge_attribute_specs_come_from_the_edge_models() -> None:
    spec = RELATIONSHIP_SPECS[RelationshipType.DROPS]
    assert {attribute.key for attribute in spec.edge_attributes} == set(
        DropEdgeAttributes.model_fields
    ) | set(DropEdgeAttributes.model_computed_fields)


def test_a_chance_is_declared_so_nobody_has_to_divide_two_numbers() -> None:
    spec = RELATIONSHIP_SPECS[RelationshipType.DROPS]
    declared = {attribute.key: attribute for attribute in spec.edge_attributes}
    chance = declared["chance"]
    assert chance.derived is True
    assert chance.prominent is True
    assert chance.format is AttributeFormat.RATE


def test_a_chance_is_never_written_down_as_though_a_source_said_it() -> None:
    from wiki_api.domain.attributes import computed_keys

    attributes = DropEdgeAttributes(weight=1.0, denominator=128.0)
    assert attributes.chance == 1 / 128
    stored = attributes.model_dump(exclude=computed_keys(DropEdgeAttributes))
    assert "chance" not in stored


def test_an_edge_still_reads_back_from_what_was_written_down() -> None:
    from wiki_api.domain.attributes import computed_keys

    attributes = DropEdgeAttributes(weight=1.0, denominator=128.0)
    stored = attributes.model_dump_json(exclude=computed_keys(DropEdgeAttributes))
    assert DropEdgeAttributes.model_validate_json(stored) == attributes


def test_a_drop_edge_keeps_weight_and_denominator_rather_than_a_rate() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.NPC, id=50),
        rel=RelationshipType.DROPS,
        dst=EntityKey(type=EntityType.ITEM, id=7980),
        attributes=DropEdgeAttributes(
            weight=1.0, denominator=128.0, table_kind=DropTableKind.TERTIARY
        ),
        provenance=_provenance(),
    )
    assert edge.attributes.model_dump()["denominator"] == 128.0
    assert isinstance(edge.attributes, DropEdgeAttributes)
    assert edge.attributes.one_in == 128.0
    assert edge.attributes.rate == 1 / 128


def test_edges_are_validated_against_the_registry() -> None:
    import pytest

    with pytest.raises(ValueError):
        Edge(
            src=EntityKey(type=EntityType.ITEM, id=4587),
            rel=RelationshipType.DROPS,
            dst=EntityKey(type=EntityType.ITEM, id=536),
            attributes=DropEdgeAttributes(weight=1.0, denominator=2.0),
            provenance=_provenance(),
        )
    with pytest.raises(ValueError):
        Edge(
            src=EntityKey(type=EntityType.NPC, id=50),
            rel=RelationshipType.DROPS,
            dst=EntityKey(type=EntityType.NPC, id=51),
            attributes=DropEdgeAttributes(weight=1.0, denominator=2.0),
            provenance=_provenance(),
        )


def test_edge_attributes_are_never_the_wrong_shape_for_the_relationship() -> None:
    import pytest

    with pytest.raises(ValueError):
        Edge(
            src=EntityKey(type=EntityType.SHOP, id=53),
            rel=RelationshipType.SELLS,
            dst=EntityKey(type=EntityType.ITEM, id=9440),
            attributes=RewardEdgeAttributes(amount=1),
            provenance=_provenance(),
        )


def test_raw_edge_attributes_are_coerced_by_relationship() -> None:
    edge = Edge.model_validate(
        {
            "src": {"type": "shop", "id": 53},
            "rel": "sells",
            "dst": {"type": "item", "id": 9440},
            "attributes": {"stock_amount": 10, "price": 100},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    assert isinstance(edge.attributes, SellEdgeAttributes)
    assert edge.attributes.currency == COINS


def test_a_shop_may_price_its_stock_in_something_other_than_coins() -> None:
    tokkul = EntityKey(type=EntityType.ITEM, id=6529)
    attributes = SellEdgeAttributes.model_validate(
        {"stock_amount": 5, "currency": 6529}
    )
    assert attributes.currency == tokkul


def test_a_relationship_without_attributes_is_still_valid() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.SHOP, id=53),
        rel=RelationshipType.STAFFED_BY,
        dst=EntityKey(type=EntityType.NPC, id=4559),
        attributes=StaffedByEdgeAttributes(),
        provenance=_provenance(),
    )
    assert edge.spec.inverse_label == "Runs shop"
    assert edge.spec.edge_attributes == ()


def test_a_weight_above_the_denominator_is_impossible() -> None:
    import pytest

    with pytest.raises(ValueError):
        DropEdgeAttributes(weight=200.0, denominator=128.0)


def test_a_relationship_may_join_two_entities_of_the_same_type() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.ITEM, id=767),
        rel=RelationshipType.USES_AMMUNITION,
        dst=EntityKey(type=EntityType.ITEM, id=877),
        attributes=AmmunitionEdgeAttributes(),
        provenance=_provenance(),
    )
    assert edge.spec.forward_label == "Uses ammunition"
    assert edge.spec.inverse_label == "Used by"


def test_an_entity_may_be_related_to_itself() -> None:
    holy_water = EntityKey(type=EntityType.ITEM, id=732)
    edge = Edge(
        src=holy_water,
        rel=RelationshipType.USES_AMMUNITION,
        dst=holy_water,
        attributes=AmmunitionEdgeAttributes(),
        provenance=_provenance(),
    )
    assert edge.src == edge.dst


def test_a_same_type_relationship_still_rejects_the_wrong_types() -> None:
    import pytest

    with pytest.raises(ValueError):
        Edge(
            src=EntityKey(type=EntityType.NPC, id=50),
            rel=RelationshipType.USES_AMMUNITION,
            dst=EntityKey(type=EntityType.ITEM, id=877),
            attributes=AmmunitionEdgeAttributes(),
            provenance=_provenance(),
        )


def _spawn(**overrides: Any) -> Edge:
    at = Coordinate(x=2273, y=4698, plane=0)
    payload: dict[str, Any] = {
        "src": EntityKey(type=EntityType.NPC, id=50),
        "rel": RelationshipType.LOCATED_IN,
        "dst": EntityKey(type=EntityType.LOCATION, id=1),
        "attributes": LocatedInEdgeAttributes(at=at),
        "provenance": _provenance(),
    }
    payload.update(overrides)
    return Edge(**payload)


def test_a_spawn_edge_places_an_entity_on_the_map() -> None:
    edge = _spawn()
    assert isinstance(edge.attributes, LocatedInEdgeAttributes)
    assert edge.attributes.at is not None
    assert edge.attributes.at.region_id == 9033
    assert edge.spec.inverse_label == "Found here"


def test_two_spawns_in_one_place_stay_distinct_without_a_counter() -> None:
    first = _spawn(attributes=LocatedInEdgeAttributes(at=Coordinate(x=3093, y=3509)))
    second = _spawn(attributes=LocatedInEdgeAttributes(at=Coordinate(x=3098, y=3508)))
    assert first.discriminator != second.discriminator


def test_a_spawn_is_keyed_by_its_position_so_a_reorder_cannot_move_it() -> None:
    edge = _spawn()
    assert edge.discriminator == "2273:4698:0"


def test_a_key_that_disagrees_with_the_edge_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        _spawn(discriminator="0")


def test_a_drop_is_keyed_by_the_table_it_rolls_from() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.NPC, id=50),
        rel=RelationshipType.DROPS,
        dst=EntityKey(type=EntityType.ITEM, id=536),
        attributes=DropEdgeAttributes(
            weight=1.0, denominator=128.0, table_kind=DropTableKind.TERTIARY
        ),
        provenance=_provenance(),
    )
    assert edge.discriminator == "tertiary"


def test_a_drop_key_can_no_longer_contradict_its_table() -> None:
    import pytest

    with pytest.raises(ValueError):
        Edge.model_validate(
            {
                "src": {"type": "npc", "id": 50},
                "rel": "drops",
                "dst": {"type": "item", "id": 536},
                "discriminator": "main",
                "attributes": {
                    "weight": 1.0,
                    "denominator": 128.0,
                    "table_kind": "tertiary",
                },
                "provenance": {"source": "fixture", "game_version": "test"},
            }
        )


def test_a_relationship_that_needs_no_key_carries_none() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.SHOP, id=53),
        rel=RelationshipType.STAFFED_BY,
        dst=EntityKey(type=EntityType.NPC, id=4559),
        attributes=StaffedByEdgeAttributes(),
        provenance=_provenance(),
    )
    assert edge.discriminator == ""


def test_a_placement_without_an_exact_tile_needs_no_discriminator() -> None:
    edge = _spawn(
        src=EntityKey(type=EntityType.SHOP, id=53),
        attributes=LocatedInEdgeAttributes(spawn_kind=SpawnKind.SHOP_FRONT),
    )
    assert isinstance(edge.attributes, LocatedInEdgeAttributes)
    assert edge.attributes.at is None
    assert edge.attributes.spawn_kind is SpawnKind.SHOP_FRONT
    assert edge.discriminator == ""


def test_only_a_location_can_be_the_place_something_is_found_in() -> None:
    import pytest

    with pytest.raises(ValueError):
        _spawn(dst=EntityKey(type=EntityType.NPC, id=51))


def test_a_location_hierarchy_reads_naturally_in_both_directions() -> None:
    edge = Edge(
        src=EntityKey(type=EntityType.LOCATION, id=2),
        rel=RelationshipType.PART_OF,
        dst=EntityKey(type=EntityType.LOCATION, id=1),
        attributes=PartOfEdgeAttributes(),
        provenance=_provenance(),
    )
    assert edge.spec.forward_label == "Part of"
    assert edge.spec.inverse_label == "Contains"


def test_a_location_cannot_be_part_of_itself() -> None:
    import pytest

    place = EntityKey(type=EntityType.LOCATION, id=1)
    with pytest.raises(ValueError):
        Edge(
            src=place,
            rel=RelationshipType.PART_OF,
            dst=place,
            attributes=PartOfEdgeAttributes(),
            provenance=_provenance(),
        )
