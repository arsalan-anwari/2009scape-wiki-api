"""Turning stored attributes into values a reader can show.

Nothing here names a field. It walks the registry, takes whatever the record happens to
carry, and attaches the presentation facts declared for each one, so an attribute added
upstream appears on the page with no change here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import AttributeValue
from wiki_api.domain.attributes import ATTRIBUTE_SPECS
from wiki_api.domain.relationships import RELATIONSHIP_SPECS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pydantic import BaseModel, JsonValue

    from wiki_api.domain.attributes import AttributeSpec
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.relationships import Edge


def declared_values(
    specs: Sequence[AttributeSpec], recorded: Mapping[str, JsonValue]
) -> tuple[AttributeValue, ...]:
    """The values a record holds, in the order the registry publishes them."""
    return tuple(
        AttributeValue.of(spec, recorded[spec.key])
        for spec in specs
        if spec.display and spec.key in recorded
    )


def entity_values(entity: Entity) -> tuple[AttributeValue, ...]:
    """Everything an entity records that a reader is allowed to see."""
    return declared_values(ATTRIBUTE_SPECS[entity.type], _recorded(entity.attributes))


def edge_values(edge: Edge) -> tuple[AttributeValue, ...]:
    """Everything a relationship records about itself."""
    return declared_values(
        RELATIONSHIP_SPECS[edge.rel].edge_attributes, _recorded(edge.attributes)
    )


def prominent_values(values: Sequence[AttributeValue]) -> tuple[AttributeValue, ...]:
    """The few values worth showing on hover."""
    return tuple(value for value in values if value.prominent)


def _recorded(attributes: BaseModel) -> Mapping[str, JsonValue]:
    recorded: Mapping[str, JsonValue] = attributes.model_dump(
        mode="json", exclude_none=True
    )
    return recorded


# test cases


def _item() -> Entity:
    from wiki_api.domain.entity import Entity

    return Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {
                "tradeable": True,
                "ge_buy_limit": 10,
                "shop_price": 100,
                "equipment_slot": 3,
                "weapon_interface": 18,
            },
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )


def test_values_come_back_in_the_order_the_registry_declares() -> None:
    orders = [value.order for value in entity_values(_item())]
    assert orders == sorted(orders)


def test_an_attribute_the_record_does_not_carry_is_absent() -> None:
    keys = {value.key for value in entity_values(_item())}
    assert "lendable" not in keys


def test_an_internal_attribute_never_reaches_a_reader() -> None:
    keys = {value.key for value in entity_values(_item())}
    assert "weapon_interface" not in keys


def test_a_vocabulary_arrives_as_its_clean_name_with_its_choices() -> None:
    values = {value.key: value for value in entity_values(_item())}
    slot = values["equipment_slot"]
    assert slot.value == "weapon"
    assert slot.choices is not None
    assert "shield" in slot.choices


def test_only_the_prominent_values_reach_a_hover() -> None:
    values = entity_values(_item())
    prominent = prominent_values(values)
    assert prominent
    assert len(prominent) < len(values)
    assert all(value.prominent for value in prominent)


def test_a_relationship_carries_its_own_values() -> None:
    from wiki_api.domain.relationships import Edge

    edge = Edge.model_validate(
        {
            "src": {"type": "npc", "id": 50},
            "rel": "drops",
            "dst": {"type": "item", "id": 536},
            "attributes": {"weight": 1.0, "denominator": 128.0},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    values = {value.key: value for value in edge_values(edge)}
    assert values["denominator"].value == 128.0
    assert values["denominator"].label == "Out of"


def test_a_reference_keeps_its_identity_rather_than_becoming_a_number() -> None:
    from wiki_api.domain.relationships import Edge

    edge = Edge.model_validate(
        {
            "src": {"type": "shop", "id": 53},
            "rel": "sells",
            "dst": {"type": "item", "id": 9440},
            "attributes": {"stock_amount": 10, "price": 8},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    values = {value.key: value for value in edge_values(edge)}
    assert values["currency"].value == {"type": "item", "id": 995}


def test_a_relationship_that_records_nothing_yields_nothing() -> None:
    from wiki_api.domain.relationships import Edge

    edge = Edge.model_validate(
        {
            "src": {"type": "shop", "id": 53},
            "rel": "staffed_by",
            "dst": {"type": "npc", "id": 4559},
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    assert edge_values(edge) == ()
