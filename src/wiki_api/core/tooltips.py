"""The hover sized answer: what this is, in as few values as the registry allows.

A tooltip is the most cached thing a reader asks for, so it stays small on purpose. It
never counts relationships, because counting them costs a query per hover.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import Tooltip
from wiki_api.core.values import entity_values, prominent_values

if TYPE_CHECKING:
    from wiki_api.domain.entity import Entity


def preview(entity: Entity) -> Tooltip:
    """The smallest honest description of an entity."""
    return Tooltip(
        link=entity.to_link(),
        type=entity.type,
        description=entity.description,
        attributes=prominent_values(entity_values(entity)),
    )


# test cases


def _entity(**overrides: object) -> Entity:
    from wiki_api.domain.entity import Entity

    payload: dict[str, object] = {
        "key": {"type": "npc", "id": 50},
        "slug": "king-black-dragon",
        "name": "King Black Dragon",
        "description": "A very large dragon.",
        "attributes": {
            "combat_level": 276,
            "lifepoints": 240,
            "attack_level": 240,
            "defence_animation": 89,
        },
        "provenance": {"source": "fixture", "game_version": "test"},
    }
    payload.update(overrides)
    return Entity.model_validate(payload)


def test_a_tooltip_carries_identity_a_description_and_a_few_values() -> None:
    tooltip = preview(_entity())
    assert tooltip.link.label == "King Black Dragon"
    assert tooltip.description == "A very large dragon."
    assert {value.key for value in tooltip.attributes} == {"combat_level", "lifepoints"}


def test_a_tooltip_leaves_out_what_is_not_worth_hovering_over() -> None:
    keys = {value.key for value in preview(_entity()).attributes}
    assert "attack_level" not in keys
    assert "defence_animation" not in keys


def test_a_tooltip_says_a_computed_value_is_computed() -> None:
    values = {value.key: value for value in preview(_entity()).attributes}
    assert values["combat_level"].derived is True
    assert values["lifepoints"].derived is False


def test_an_entity_with_nothing_recorded_still_previews() -> None:
    tooltip = preview(_entity(attributes={}, description=None))
    assert tooltip.attributes == ()
    assert tooltip.description is None
    assert tooltip.link.label == "King Black Dragon"
