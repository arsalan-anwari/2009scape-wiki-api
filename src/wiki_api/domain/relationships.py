from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.attributes import (
    AttributeFormat,
    AttributeMeta,
    AttributeSpec,
    specs_of,
)
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.provenance import Provenance

if TYPE_CHECKING:
    from collections.abc import Mapping


class RelationshipType(StrEnum):
    DROPS = "drops"
    SELLS = "sells"
    STAFFED_BY = "staffed_by"
    REWARDS = "rewards"
    USES_AMMUNITION = "uses_ammunition"


class DropTableKind(StrEnum):
    DEFAULT = "default"
    MAIN = "main"
    CHARM = "charm"
    TERTIARY = "tertiary"


class DropEdgeAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    weight: Annotated[
        float,
        AttributeMeta("Weight", "rate", 10, AttributeFormat.FLOAT),
    ] = Field(gt=0.0)
    denominator: Annotated[
        float,
        AttributeMeta("Out of", "rate", 20, AttributeFormat.FLOAT),
    ] = Field(gt=0.0)
    table_kind: Annotated[
        DropTableKind,
        AttributeMeta("Drop table", "rate", 30, AttributeFormat.TEXT),
    ] = DropTableKind.MAIN
    min_amount: Annotated[
        int,
        AttributeMeta("Minimum amount", "amount", 40, AttributeFormat.INT),
    ] = Field(default=1, ge=1)
    max_amount: Annotated[
        int,
        AttributeMeta("Maximum amount", "amount", 50, AttributeFormat.INT),
    ] = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.max_amount < self.min_amount:
            raise ValueError("max_amount must not be below min_amount")
        if self.weight > self.denominator:
            raise ValueError("weight must not exceed the denominator")
        return self

    @property
    def rate(self) -> float:
        return self.weight / self.denominator

    @property
    def one_in(self) -> float:
        return self.denominator / self.weight


class SellEdgeAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stock_amount: Annotated[
        int,
        AttributeMeta("Stock", "shop", 10, AttributeFormat.INT),
    ] = Field(ge=0)
    restock_rate: Annotated[
        int,
        AttributeMeta("Restock rate", "shop", 20, AttributeFormat.INT),
    ] = Field(default=100, ge=0)
    price: Annotated[
        int | None,
        AttributeMeta("Price", "shop", 30, AttributeFormat.GP),
    ] = None
    currency_item_id: Annotated[
        int,
        AttributeMeta("Currency", "shop", 40, AttributeFormat.ID),
    ] = Field(default=995, ge=0)
    slot: Annotated[
        int,
        AttributeMeta("Slot", "shop", 50, AttributeFormat.INT, display=False),
    ] = Field(default=0, ge=0)


class StaffedByEdgeAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RewardEdgeAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Annotated[
        int,
        AttributeMeta("Amount", "reward", 10, AttributeFormat.INT),
    ] = Field(default=1, ge=1)


class AmmunitionEdgeAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


EdgeAttributes = (
    DropEdgeAttributes
    | SellEdgeAttributes
    | StaffedByEdgeAttributes
    | RewardEdgeAttributes
    | AmmunitionEdgeAttributes
)

EDGE_ATTRIBUTE_MODELS: Final[Mapping[RelationshipType, type[EdgeAttributes]]] = {
    RelationshipType.DROPS: DropEdgeAttributes,
    RelationshipType.SELLS: SellEdgeAttributes,
    RelationshipType.STAFFED_BY: StaffedByEdgeAttributes,
    RelationshipType.REWARDS: RewardEdgeAttributes,
    RelationshipType.USES_AMMUNITION: AmmunitionEdgeAttributes,
}


class RelationshipSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    rel: RelationshipType
    forward_label: str
    inverse_label: str
    src_types: frozenset[EntityType]
    dst_types: frozenset[EntityType]
    edge_attributes: tuple[AttributeSpec, ...]
    group: str
    order: int


def _spec(
    rel: RelationshipType,
    forward_label: str,
    inverse_label: str,
    src_types: frozenset[EntityType],
    dst_types: frozenset[EntityType],
    group: str,
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
        "drops",
        10,
    ),
    RelationshipType.SELLS: _spec(
        RelationshipType.SELLS,
        "Sells",
        "Sold in",
        frozenset({EntityType.SHOP}),
        frozenset({EntityType.ITEM}),
        "trade",
        20,
    ),
    RelationshipType.STAFFED_BY: _spec(
        RelationshipType.STAFFED_BY,
        "Staffed by",
        "Runs shop",
        frozenset({EntityType.SHOP}),
        frozenset({EntityType.NPC}),
        "trade",
        30,
    ),
    RelationshipType.REWARDS: _spec(
        RelationshipType.REWARDS,
        "Rewards",
        "Reward from",
        frozenset({EntityType.QUEST}),
        frozenset({EntityType.ITEM}),
        "quests",
        40,
    ),
    RelationshipType.USES_AMMUNITION: _spec(
        RelationshipType.USES_AMMUNITION,
        "Uses ammunition",
        "Used by",
        frozenset({EntityType.ITEM}),
        frozenset({EntityType.ITEM}),
        "equipment",
        50,
    ),
}


class Edge(BaseModel):
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
    def _coerce_attributes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("attributes")
        rel = data.get("rel")
        if isinstance(raw, dict) and rel is not None:
            model = EDGE_ATTRIBUTE_MODELS[RelationshipType(rel)]
            return {**data, "attributes": model.model_validate(raw)}
        return data

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
        return self

    @property
    def spec(self) -> RelationshipSpec:
        return RELATIONSHIP_SPECS[self.rel]


def _provenance() -> Provenance:
    return Provenance(source="fixture", game_version="test")


def test_every_relationship_type_is_registered_with_both_labels() -> None:
    for rel in RelationshipType:
        spec = RELATIONSHIP_SPECS[rel]
        assert spec.forward_label and spec.inverse_label
        assert spec.forward_label != spec.inverse_label
        assert rel in EDGE_ATTRIBUTE_MODELS


def test_edge_attribute_specs_come_from_the_edge_models() -> None:
    spec = RELATIONSHIP_SPECS[RelationshipType.DROPS]
    assert {attribute.key for attribute in spec.edge_attributes} == set(
        DropEdgeAttributes.model_fields
    )


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
    assert edge.attributes.currency_item_id == 995


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
