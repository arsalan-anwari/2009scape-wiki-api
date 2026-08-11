"""Turn stored fields into values a reader can show, by walking the registry rather
than naming any of them.

Given a `Naming`, a value pointing at another entity comes back as a whole link
rather than a bare key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import AttributeValue
from wiki_api.domain.attributes import ATTRIBUTE_SPECS, stored_at
from wiki_api.domain.identity import EntityKey
from wiki_api.domain.relationships import RELATIONSHIP_SPECS
from wiki_api.domain.vocabulary import AttributeFormat

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from pydantic import BaseModel, JsonValue

    from wiki_api.domain.attributes import AttributeSpec
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import Link
    from wiki_api.domain.query import Comparable
    from wiki_api.domain.relationships import Edge
    from wiki_api.repository.protocol import KnowledgeRepository

type Naming = Callable[[Sequence[EntityKey]], Mapping[EntityKey, Link]]


def naming_of(repository: KnowledgeRepository) -> Naming:
    """Build the lookup a pointing value needs, remembering what it has already asked
    so a whole page costs one question per distinct thing pointed at.
    """
    known: dict[EntityKey, Link] = {}

    def named(keys: Sequence[EntityKey]) -> Mapping[EntityKey, Link]:
        missing = tuple(dict.fromkeys(key for key in keys if key not in known))
        if missing:
            known.update(
                (key, entity.to_link())
                for key, entity in repository.get_entities(missing).items()
            )
        return {key: known[key] for key in keys if key in known}

    return named


def declared_values(
    specs: Sequence[AttributeSpec],
    recorded: Mapping[str, JsonValue],
    naming: Naming | None = None,
) -> tuple[AttributeValue, ...]:
    """Read the values a record holds, in the order the registry publishes them."""
    values = tuple(
        AttributeValue.of(spec, recorded[spec.key])
        for spec in specs
        if spec.display and spec.key in recorded
    )
    return values if naming is None else linked(values, naming)


def entity_values(
    entity: Entity, naming: Naming | None = None
) -> tuple[AttributeValue, ...]:
    """Read everything an entity records that a reader may see."""
    return declared_values(
        ATTRIBUTE_SPECS[entity.type], _recorded(entity.attributes), naming
    )


def compared_values(
    entity: Entity, shown: Sequence[Comparable]
) -> tuple[AttributeValue, ...]:
    """Read back the values a comparison was made on, keyed by how they were asked
    for.
    """
    read = (
        (one, stored_at(entity.attributes, one.path)) for one in dict.fromkeys(shown)
    )
    return tuple(
        AttributeValue.of(one.spec, held).model_copy(update={"key": one.path})
        for one, held in read
        if isinstance(held, int | float) and not isinstance(held, bool)
    )


def edge_values(edge: Edge, naming: Naming | None = None) -> tuple[AttributeValue, ...]:
    """Read everything a relationship records about itself."""
    return declared_values(
        RELATIONSHIP_SPECS[edge.rel].edge_attributes, _recorded(edge.attributes), naming
    )


def linked(
    values: Sequence[AttributeValue], naming: Naming
) -> tuple[AttributeValue, ...]:
    """Turn every value that points at an entity into the whole link it stands for."""
    wanted = {key for key in map(_pointed_at, values) if key is not None}
    if not wanted:
        return tuple(values)
    found = naming(sorted(wanted, key=str))
    return tuple(_linked(value, found) for value in values)


def prominent_values(values: Sequence[AttributeValue]) -> tuple[AttributeValue, ...]:
    """Read the few values worth showing on hover."""
    return tuple(value for value in values if value.prominent)


def _pointed_at(value: AttributeValue) -> EntityKey | None:
    if value.format is not AttributeFormat.REF or not isinstance(value.value, dict):
        return None
    try:
        return EntityKey.model_validate(value.value)
    except ValueError:
        return None


def _linked(value: AttributeValue, found: Mapping[EntityKey, Link]) -> AttributeValue:
    key = _pointed_at(value)
    link = None if key is None else found.get(key)
    if link is None:
        return value
    return value.model_copy(update={"value": link.model_dump(mode="json")})


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
                "render_anim": 18,
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
    assert "render_anim" not in keys


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


def _shop_edge() -> Edge:
    from wiki_api.domain.relationships import Edge

    return Edge.model_validate(
        {
            "src": {"type": "shop", "id": 53},
            "rel": "sells",
            "dst": {"type": "item", "id": 9440},
            "attributes": {"stock_amount": 10, "price": 8},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )


def _coins_link() -> Link:
    from wiki_api.domain.identity import EntityType, Link

    return Link(type=EntityType.ITEM, id=995, slug="coins", label="Coins")


def _coins() -> Naming:
    coins = _coins_link()

    def named(keys: Sequence[EntityKey]) -> Mapping[EntityKey, Link]:
        return {key: coins for key in keys if key == coins.key}

    return named


def test_a_pointing_value_arrives_as_something_a_reader_can_read() -> None:
    values = {value.key: value for value in edge_values(_shop_edge(), _coins())}
    assert values["currency"].value == {
        "type": "item",
        "id": 995,
        "slug": "coins",
        "label": "Coins",
        "icon_ref": None,
    }


def test_a_pointing_value_nothing_answers_for_keeps_what_it_had() -> None:

    def named(keys: Sequence[EntityKey]) -> Mapping[EntityKey, Link]:
        return {}

    values = {value.key: value for value in edge_values(_shop_edge(), named)}
    assert values["currency"].value == {"type": "item", "id": 995}


def test_a_record_that_points_at_nothing_asks_nothing() -> None:
    asked: list[int] = []

    def named(keys: Sequence[EntityKey]) -> Mapping[EntityKey, Link]:
        asked.append(len(keys))
        return {}

    entity_values(_item(), named)
    assert asked == []


def _holding_coins() -> tuple[KnowledgeRepository, list[int]]:
    from typing import cast

    from wiki_api.domain.entity import Entity

    coins = Entity.model_validate(
        {
            "key": {"type": "item", "id": 995},
            "slug": "coins",
            "name": "Coins",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    asked: list[int] = []

    class Counting:
        def get_entities(self, keys: Sequence[EntityKey]) -> Mapping[EntityKey, Entity]:
            asked.append(len(keys))
            return {key: coins for key in keys if key == coins.key}

    return cast("KnowledgeRepository", Counting()), asked


def test_the_same_thing_pointed_at_twice_is_only_asked_for_once() -> None:
    repository, asked = _holding_coins()
    naming = naming_of(repository)
    edge_values(_shop_edge(), naming)
    edge_values(_shop_edge(), naming)
    assert asked == [1]


def test_a_lookup_answers_for_what_it_was_asked_about_a_second_time() -> None:
    repository, _ = _holding_coins()
    naming = naming_of(repository)
    naming([EntityKey.parse("item:995")])
    assert (
        naming([EntityKey.parse("item:995")])[EntityKey.parse("item:995")].label
        == "Coins"
    )
