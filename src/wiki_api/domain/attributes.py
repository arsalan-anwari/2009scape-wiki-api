from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.identity import EntityType
from wiki_api.domain.space import Area, Coordinate, LocationKind

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
    COORD = "coord"
    AREA = "area"


@dataclass(frozen=True)
class AttributeMeta:
    label: str
    group: str
    order: int
    format: AttributeFormat
    unit: str | None = None
    display: bool = True
    derived: bool = False


class AttributeSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    group: str
    order: int
    format: AttributeFormat
    unit: str | None = None
    display: bool = True
    derived: bool = False


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
                derived=meta.derived,
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
    alchemizable: Annotated[
        bool | None,
        AttributeMeta("Alchemizable", "trade", 32, AttributeFormat.BOOL),
    ] = None
    high_alch_value: Annotated[
        int | None,
        AttributeMeta("High alchemy", "trade", 34, AttributeFormat.GP, derived=True),
    ] = None
    low_alch_value: Annotated[
        int | None,
        AttributeMeta("Low alchemy", "trade", 36, AttributeFormat.GP, derived=True),
    ] = None
    lendable: Annotated[
        bool | None,
        AttributeMeta("Lendable", "trade", 40, AttributeFormat.BOOL),
    ] = None
    archery_ticket_price: Annotated[
        int | None,
        AttributeMeta("Archery ticket price", "trade", 50, AttributeFormat.INT),
    ] = None
    tokkul_price: Annotated[
        int | None,
        AttributeMeta("Tokkul price", "trade", 52, AttributeFormat.INT),
    ] = None
    castle_wars_ticket_price: Annotated[
        int | None,
        AttributeMeta("Castle Wars ticket price", "trade", 54, AttributeFormat.INT),
    ] = None
    point_price: Annotated[
        int | None,
        AttributeMeta("Point price", "trade", 56, AttributeFormat.INT),
    ] = None
    weight: Annotated[
        float | None,
        AttributeMeta("Weight", "general", 60, AttributeFormat.FLOAT, unit="kg"),
    ] = None
    bankable: Annotated[
        bool | None,
        AttributeMeta("Bankable", "general", 62, AttributeFormat.BOOL),
    ] = None
    rare_item: Annotated[
        bool | None,
        AttributeMeta("Rare item", "general", 64, AttributeFormat.BOOL),
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
    two_handed: Annotated[
        bool | None,
        AttributeMeta("Two-handed", "equipment", 92, AttributeFormat.BOOL),
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
    fun_weapon: Annotated[
        bool | None,
        AttributeMeta("Fun weapon", "equipment", 145, AttributeFormat.BOOL),
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
    hat: Annotated[
        bool | None,
        AttributeMeta("Hat", "internal", 230, AttributeFormat.BOOL, display=False),
    ] = None
    remove_head: Annotated[
        bool | None,
        AttributeMeta(
            "Hides head", "internal", 232, AttributeFormat.BOOL, display=False
        ),
    ] = None
    remove_sleeves: Annotated[
        bool | None,
        AttributeMeta(
            "Hides sleeves", "internal", 234, AttributeFormat.BOOL, display=False
        ),
    ] = None
    remove_beard: Annotated[
        bool | None,
        AttributeMeta(
            "Hides beard", "internal", 236, AttributeFormat.BOOL, display=False
        ),
    ] = None
    attack_anims: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Attack animations", "internal", 240, AttributeFormat.IDS, display=False
        ),
    ] = None
    defence_anim: Annotated[
        int | None,
        AttributeMeta(
            "Defence animation", "internal", 242, AttributeFormat.ID, display=False
        ),
    ] = None
    walk_anim: Annotated[
        int | None,
        AttributeMeta(
            "Walk animation", "internal", 244, AttributeFormat.ID, display=False
        ),
    ] = None
    run_anim: Annotated[
        int | None,
        AttributeMeta(
            "Run animation", "internal", 246, AttributeFormat.ID, display=False
        ),
    ] = None
    stand_anim: Annotated[
        int | None,
        AttributeMeta(
            "Stand animation", "internal", 248, AttributeFormat.ID, display=False
        ),
    ] = None
    stand_turn_anim: Annotated[
        int | None,
        AttributeMeta(
            "Stand-turn animation", "internal", 250, AttributeFormat.ID, display=False
        ),
    ] = None
    turn90cw_anim: Annotated[
        int | None,
        AttributeMeta(
            "Turn 90 clockwise", "internal", 252, AttributeFormat.ID, display=False
        ),
    ] = None
    turn90ccw_anim: Annotated[
        int | None,
        AttributeMeta(
            "Turn 90 anticlockwise", "internal", 254, AttributeFormat.ID, display=False
        ),
    ] = None
    turn180_anim: Annotated[
        int | None,
        AttributeMeta("Turn 180", "internal", 256, AttributeFormat.ID, display=False),
    ] = None
    attack_audios: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Attack audio", "internal", 258, AttributeFormat.IDS, display=False
        ),
    ] = None


class NpcAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    combat_level: Annotated[
        int | None,
        AttributeMeta("Combat level", "combat", 5, AttributeFormat.INT, derived=True),
    ] = None
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
    attack_speed: Annotated[
        int | None,
        AttributeMeta("Attack speed", "combat", 65, AttributeFormat.INT, unit="ticks"),
    ] = None
    bonuses: Annotated[
        tuple[int, ...] | None,
        AttributeMeta("Combat bonuses", "combat", 70, AttributeFormat.INTS),
    ] = None
    combat_style: Annotated[
        int | None,
        AttributeMeta("Combat style", "combat", 75, AttributeFormat.INT),
    ] = None
    weakness: Annotated[
        int | None,
        AttributeMeta("Weakness", "combat", 80, AttributeFormat.INT),
    ] = None
    protect_style: Annotated[
        int | None,
        AttributeMeta("Protection style", "combat", 85, AttributeFormat.INT),
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
    poisonous: Annotated[
        bool | None,
        AttributeMeta("Poisonous", "behaviour", 132, AttributeFormat.BOOL),
    ] = None
    poison_amount: Annotated[
        int | None,
        AttributeMeta("Poison damage", "behaviour", 134, AttributeFormat.INT),
    ] = None
    poison_immune: Annotated[
        bool | None,
        AttributeMeta("Immune to poison", "behaviour", 136, AttributeFormat.BOOL),
    ] = None
    movement_radius: Annotated[
        int | None,
        AttributeMeta(
            "Movement radius", "behaviour", 138, AttributeFormat.INT, unit="tiles"
        ),
    ] = None
    can_tolerate: Annotated[
        bool | None,
        AttributeMeta("Becomes tolerant", "behaviour", 139, AttributeFormat.BOOL),
    ] = None
    clue_level: Annotated[
        int | None,
        AttributeMeta("Clue scroll level", "drops", 140, AttributeFormat.INT),
    ] = None
    slayer_task: Annotated[
        int | None,
        AttributeMeta("Slayer task", "drops", 145, AttributeFormat.ID),
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
    spawn_animation: Annotated[
        int | None,
        AttributeMeta(
            "Spawn animation", "internal", 260, AttributeFormat.ID, display=False
        ),
    ] = None
    death_gfx: Annotated[
        int | None,
        AttributeMeta(
            "Death graphic", "internal", 262, AttributeFormat.ID, display=False
        ),
    ] = None
    start_gfx: Annotated[
        int | None,
        AttributeMeta(
            "Start graphic", "internal", 264, AttributeFormat.ID, display=False
        ),
    ] = None
    end_gfx: Annotated[
        int | None,
        AttributeMeta(
            "End graphic", "internal", 266, AttributeFormat.ID, display=False
        ),
    ] = None
    projectile: Annotated[
        int | None,
        AttributeMeta("Projectile", "internal", 268, AttributeFormat.ID, display=False),
    ] = None
    prj_height: Annotated[
        int | None,
        AttributeMeta(
            "Projectile height", "internal", 270, AttributeFormat.INT, display=False
        ),
    ] = None
    start_height: Annotated[
        int | None,
        AttributeMeta(
            "Start height", "internal", 272, AttributeFormat.INT, display=False
        ),
    ] = None
    end_height: Annotated[
        int | None,
        AttributeMeta(
            "End height", "internal", 274, AttributeFormat.INT, display=False
        ),
    ] = None
    spell_id: Annotated[
        int | None,
        AttributeMeta("Spell", "internal", 276, AttributeFormat.ID, display=False),
    ] = None
    water_npc: Annotated[
        bool | None,
        AttributeMeta(
            "Lives in water", "internal", 278, AttributeFormat.BOOL, display=False
        ),
    ] = None
    facing_booth: Annotated[
        bool | None,
        AttributeMeta(
            "Faces a booth", "internal", 280, AttributeFormat.BOOL, display=False
        ),
    ] = None
    force_talk: Annotated[
        str | None,
        AttributeMeta(
            "Forced dialogue", "internal", 282, AttributeFormat.TEXT, display=False
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


class LocationAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[
        LocationKind | None,
        AttributeMeta("Kind", "overview", 10, AttributeFormat.TEXT),
    ] = None
    centre: Annotated[
        Coordinate | None,
        AttributeMeta("Centre", "map", 20, AttributeFormat.COORD),
    ] = None
    bounds: Annotated[
        Area | None,
        AttributeMeta("Extent", "map", 30, AttributeFormat.AREA),
    ] = None
    region_id: Annotated[
        int | None,
        AttributeMeta("Region", "map", 40, AttributeFormat.ID, derived=True),
    ] = None
    members: Annotated[
        bool | None,
        AttributeMeta("Members only", "overview", 50, AttributeFormat.BOOL),
    ] = None
    multicombat: Annotated[
        bool | None,
        AttributeMeta("Multicombat", "overview", 60, AttributeFormat.BOOL),
    ] = None
    wilderness_level: Annotated[
        int | None,
        AttributeMeta("Wilderness level", "overview", 70, AttributeFormat.INT),
    ] = None

    @model_validator(mode="after")
    def _check_centre_falls_inside_the_bounds(self) -> Self:
        misplaced = (
            self.bounds is not None
            and self.centre is not None
            and not self.bounds.contains(self.centre)
        )
        if misplaced:
            raise ValueError("the centre must fall inside the bounds")
        return self

    @property
    def anchor(self) -> Coordinate | None:
        if self.centre is not None:
            return self.centre
        if self.bounds is not None:
            return self.bounds.centre
        return None


EntityAttributes = (
    ItemAttributes
    | NpcAttributes
    | ShopAttributes
    | QuestAttributes
    | LocationAttributes
)

ATTRIBUTE_MODELS: Final[Mapping[EntityType, type[EntityAttributes]]] = {
    EntityType.ITEM: ItemAttributes,
    EntityType.NPC: NpcAttributes,
    EntityType.SHOP: ShopAttributes,
    EntityType.QUEST: QuestAttributes,
    EntityType.LOCATION: LocationAttributes,
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


def test_a_derived_attribute_is_declared_as_such() -> None:
    npc_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.NPC]}
    assert npc_specs["combat_level"].derived is True
    assert npc_specs["lifepoints"].derived is False


def test_the_registry_declares_every_attribute_the_sources_populate() -> None:
    item_keys = set(ItemAttributes.model_fields)
    assert {"two_handed", "bankable", "alchemizable", "rare_item"} <= item_keys
    assert {"tokkul_price", "castle_wars_ticket_price", "point_price"} <= item_keys
    npc_keys = set(NpcAttributes.model_fields)
    assert {"attack_speed", "combat_style", "protect_style"} <= npc_keys
    assert {"poisonous", "poison_amount", "poison_immune"} <= npc_keys


def test_a_location_carries_a_point_on_the_map() -> None:
    attributes = LocationAttributes.model_validate(
        {
            "kind": "dungeon",
            "centre": {"x": 2273, "y": 4698, "plane": 0},
            "region_id": 9033,
        }
    )
    assert attributes.centre is not None
    assert attributes.centre.region_id == 9033
    assert attributes.anchor == attributes.centre


def test_a_location_falls_back_to_the_centre_of_its_extent() -> None:
    attributes = LocationAttributes.model_validate(
        {"bounds": {"min_x": 3200, "min_y": 3200, "max_x": 3210, "max_y": 3220}}
    )
    assert attributes.anchor == Coordinate(x=3205, y=3210)


def test_a_location_with_nothing_on_the_map_has_no_anchor() -> None:
    assert LocationAttributes().anchor is None


def test_a_centre_outside_its_own_bounds_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        LocationAttributes.model_validate(
            {
                "centre": {"x": 9999, "y": 9999},
                "bounds": {"min_x": 3200, "min_y": 3200, "max_x": 3210, "max_y": 3220},
            }
        )


def test_the_map_formats_are_declared_for_the_front_end() -> None:
    location_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.LOCATION]}
    assert location_specs["centre"].format is AttributeFormat.COORD
    assert location_specs["bounds"].format is AttributeFormat.AREA
