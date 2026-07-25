from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.identity import EntityType

if TYPE_CHECKING:
    from collections.abc import Mapping


class AttributeFormat(StrEnum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    TEXT = "text"
    GP = "gp"
    ID = "id"
    IDS = "ids"
    INTS = "ints"
    SKILLS = "skills"


@dataclass(frozen=True)
class AttributeMeta:
    label: str
    group: str
    order: int
    format: AttributeFormat
    unit: str | None = None
    display: bool = True


class AttributeSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    group: str
    order: int
    format: AttributeFormat
    unit: str | None = None
    display: bool = True


class MissingAttributeMeta(TypeError):
    def __init__(self, model: type[BaseModel], field: str) -> None:
        super().__init__(f"{model.__name__}.{field} declares no AttributeMeta")
        self.model = model
        self.field = field


def specs_of(model: type[BaseModel]) -> tuple[AttributeSpec, ...]:
    specs: list[AttributeSpec] = []
    for name, field in model.model_fields.items():
        meta = next(
            (entry for entry in field.metadata if isinstance(entry, AttributeMeta)),
            None,
        )
        if meta is None:
            raise MissingAttributeMeta(model, name)
        specs.append(
            AttributeSpec(
                key=name,
                label=meta.label,
                group=meta.group,
                order=meta.order,
                format=meta.format,
                unit=meta.unit,
                display=meta.display,
            )
        )
    return tuple(sorted(specs, key=lambda spec: (spec.order, spec.key)))


class SkillRequirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    skill_id: int = Field(ge=0)
    level: int = Field(ge=1, le=99)


class ItemAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tradeable: Annotated[
        bool | None,
        AttributeMeta("Tradeable", "trade", 10, AttributeFormat.BOOL),
    ] = None
    ge_buy_limit: Annotated[
        int | None,
        AttributeMeta("Buy limit", "trade", 20, AttributeFormat.INT),
    ] = None
    shop_price: Annotated[
        int | None,
        AttributeMeta("Shop price", "trade", 30, AttributeFormat.GP),
    ] = None
    lendable: Annotated[
        bool | None,
        AttributeMeta("Lendable", "trade", 40, AttributeFormat.BOOL),
    ] = None
    archery_ticket_price: Annotated[
        int | None,
        AttributeMeta("Archery ticket price", "trade", 50, AttributeFormat.INT),
    ] = None
    weight: Annotated[
        float | None,
        AttributeMeta("Weight", "general", 60, AttributeFormat.FLOAT, unit="kg"),
    ] = None
    destroy: Annotated[
        bool | None,
        AttributeMeta("Destroyed on drop", "general", 70, AttributeFormat.BOOL),
    ] = None
    destroy_message: Annotated[
        str | None,
        AttributeMeta("Destroy option", "general", 80, AttributeFormat.TEXT),
    ] = None
    equipment_slot: Annotated[
        int | None,
        AttributeMeta("Equipment slot", "equipment", 90, AttributeFormat.INT),
    ] = None
    attack_speed: Annotated[
        int | None,
        AttributeMeta(
            "Attack speed", "equipment", 100, AttributeFormat.INT, unit="ticks"
        ),
    ] = None
    has_special: Annotated[
        bool | None,
        AttributeMeta("Special attack", "equipment", 110, AttributeFormat.BOOL),
    ] = None
    bonuses: Annotated[
        tuple[int, ...] | None,
        AttributeMeta("Combat bonuses", "equipment", 120, AttributeFormat.INTS),
    ] = None
    absorb: Annotated[
        tuple[int, ...] | None,
        AttributeMeta("Absorption", "equipment", 130, AttributeFormat.INTS),
    ] = None
    requirements: Annotated[
        tuple[SkillRequirement, ...] | None,
        AttributeMeta("Requirements", "equipment", 140, AttributeFormat.SKILLS),
    ] = None
    weapon_interface: Annotated[
        int | None,
        AttributeMeta(
            "Weapon interface", "internal", 200, AttributeFormat.ID, display=False
        ),
    ] = None
    render_anim: Annotated[
        int | None,
        AttributeMeta(
            "Render animation", "internal", 210, AttributeFormat.ID, display=False
        ),
    ] = None
    equip_audio: Annotated[
        int | None,
        AttributeMeta(
            "Equip audio", "internal", 220, AttributeFormat.ID, display=False
        ),
    ] = None


class NpcAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lifepoints: Annotated[
        int | None,
        AttributeMeta("Lifepoints", "combat", 10, AttributeFormat.INT),
    ] = None
    attack_level: Annotated[
        int | None,
        AttributeMeta("Attack level", "combat", 20, AttributeFormat.INT),
    ] = None
    strength_level: Annotated[
        int | None,
        AttributeMeta("Strength level", "combat", 30, AttributeFormat.INT),
    ] = None
    defence_level: Annotated[
        int | None,
        AttributeMeta("Defence level", "combat", 40, AttributeFormat.INT),
    ] = None
    magic_level: Annotated[
        int | None,
        AttributeMeta("Magic level", "combat", 50, AttributeFormat.INT),
    ] = None
    range_level: Annotated[
        int | None,
        AttributeMeta("Ranged level", "combat", 60, AttributeFormat.INT),
    ] = None
    bonuses: Annotated[
        tuple[int, ...] | None,
        AttributeMeta("Combat bonuses", "combat", 70, AttributeFormat.INTS),
    ] = None
    weakness: Annotated[
        int | None,
        AttributeMeta("Weakness", "combat", 80, AttributeFormat.INT),
    ] = None
    slayer_exp: Annotated[
        float | None,
        AttributeMeta("Slayer experience", "combat", 90, AttributeFormat.FLOAT),
    ] = None
    aggressive: Annotated[
        bool | None,
        AttributeMeta("Aggressive", "behaviour", 100, AttributeFormat.BOOL),
    ] = None
    agg_radius: Annotated[
        int | None,
        AttributeMeta(
            "Aggression radius", "behaviour", 110, AttributeFormat.INT, unit="tiles"
        ),
    ] = None
    respawn_delay: Annotated[
        int | None,
        AttributeMeta(
            "Respawn delay", "behaviour", 120, AttributeFormat.INT, unit="ticks"
        ),
    ] = None
    safespot: Annotated[
        bool | None,
        AttributeMeta("Safespottable", "behaviour", 130, AttributeFormat.BOOL),
    ] = None
    clue_level: Annotated[
        int | None,
        AttributeMeta("Clue scroll level", "drops", 140, AttributeFormat.INT),
    ] = None
    combat_audio: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Combat audio", "internal", 200, AttributeFormat.IDS, display=False
        ),
    ] = None
    death_animation: Annotated[
        int | None,
        AttributeMeta(
            "Death animation", "internal", 210, AttributeFormat.ID, display=False
        ),
    ] = None
    defence_animation: Annotated[
        int | None,
        AttributeMeta(
            "Defence animation", "internal", 220, AttributeFormat.ID, display=False
        ),
    ] = None
    melee_animation: Annotated[
        int | None,
        AttributeMeta(
            "Melee animation", "internal", 230, AttributeFormat.ID, display=False
        ),
    ] = None
    magic_animation: Annotated[
        int | None,
        AttributeMeta(
            "Magic animation", "internal", 240, AttributeFormat.ID, display=False
        ),
    ] = None
    range_animation: Annotated[
        int | None,
        AttributeMeta(
            "Ranged animation", "internal", 250, AttributeFormat.ID, display=False
        ),
    ] = None


class ShopAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    general_store: Annotated[
        bool | None,
        AttributeMeta("General store", "shop", 10, AttributeFormat.BOOL),
    ] = None
    currency_item_id: Annotated[
        int | None,
        AttributeMeta("Currency", "shop", 20, AttributeFormat.ID),
    ] = None
    high_alch: Annotated[
        bool | None,
        AttributeMeta("Buys alchemy products", "shop", 30, AttributeFormat.BOOL),
    ] = None


class QuestAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    difficulty: Annotated[
        str | None,
        AttributeMeta("Difficulty", "overview", 10, AttributeFormat.TEXT),
    ] = None
    length: Annotated[
        str | None,
        AttributeMeta("Length", "overview", 20, AttributeFormat.TEXT),
    ] = None
    quest_points: Annotated[
        int | None,
        AttributeMeta("Quest points", "overview", 30, AttributeFormat.INT),
    ] = None
    members: Annotated[
        bool | None,
        AttributeMeta("Members only", "overview", 40, AttributeFormat.BOOL),
    ] = None
    series: Annotated[
        str | None,
        AttributeMeta("Series", "overview", 50, AttributeFormat.TEXT),
    ] = None
    start_location: Annotated[
        str | None,
        AttributeMeta("Start point", "overview", 60, AttributeFormat.TEXT),
    ] = None


EntityAttributes = ItemAttributes | NpcAttributes | ShopAttributes | QuestAttributes

ATTRIBUTE_MODELS: Final[Mapping[EntityType, type[EntityAttributes]]] = {
    EntityType.ITEM: ItemAttributes,
    EntityType.NPC: NpcAttributes,
    EntityType.SHOP: ShopAttributes,
    EntityType.QUEST: QuestAttributes,
}

ATTRIBUTE_SPECS: Final[Mapping[EntityType, tuple[AttributeSpec, ...]]] = {
    entity_type: specs_of(model) for entity_type, model in ATTRIBUTE_MODELS.items()
}


def empty_attributes(entity_type: EntityType) -> EntityAttributes:
    return ATTRIBUTE_MODELS[entity_type]()


def test_every_entity_type_has_a_model_and_a_spec_set() -> None:
    for entity_type in EntityType:
        assert entity_type in ATTRIBUTE_MODELS
        assert ATTRIBUTE_SPECS[entity_type]


def test_specs_cover_exactly_the_model_fields() -> None:
    for entity_type, model in ATTRIBUTE_MODELS.items():
        spec_keys = {spec.key for spec in ATTRIBUTE_SPECS[entity_type]}
        assert spec_keys == set(model.model_fields)


def test_specs_are_ordered_and_labelled() -> None:
    for specs in ATTRIBUTE_SPECS.values():
        orders = [spec.order for spec in specs]
        assert orders == sorted(orders)
        assert all(spec.label and spec.group for spec in specs)


def test_a_field_without_metadata_is_rejected() -> None:
    import pytest

    class Bad(BaseModel):
        oops: int | None = None

    with pytest.raises(MissingAttributeMeta):
        specs_of(Bad)


def test_internal_attributes_are_stored_but_not_displayed() -> None:
    item_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.ITEM]}
    assert item_specs["weapon_interface"].display is False
    assert item_specs["ge_buy_limit"].display is True


def test_attributes_are_sparse_frozen_and_closed() -> None:
    import pytest

    attributes = ItemAttributes(ge_buy_limit=10, tradeable=True)
    assert attributes.weight is None
    assert attributes.model_dump(exclude_none=True) == {
        "ge_buy_limit": 10,
        "tradeable": True,
    }
    with pytest.raises(ValueError):
        ItemAttributes.model_validate({"lifepoints": 240})


def test_unknown_attribute_keys_never_reach_the_model() -> None:
    import pytest

    with pytest.raises(ValueError):
        ItemAttributes.model_validate({"ge_buy_limitt": 10})
