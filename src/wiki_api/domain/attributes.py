"""The registry that says what every entity attribute means and how to show it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Self, get_args

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.space import Area, Coordinate, LocationKind
from wiki_api.domain.vocabulary import (
    COINS,
    AbsorbBonuses,
    AttributeGroup,
    ClueLevel,
    CombatBonuses,
    CombatStyle,
    EquipmentSlot,
    QuestDifficulty,
    QuestLength,
    Skill,
    Unit,
    coerce_item_ref,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class AttributeFormat(StrEnum):
    """How to draw a value: a plain number, an amount of coins, a coordinate."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    TEXT = "text"
    GP = "gp"
    ID = "id"
    IDS = "ids"
    REF = "ref"
    ENUM = "enum"
    SKILLS = "skills"
    BONUSES = "bonuses"
    ABSORB = "absorb"
    COORD = "coord"
    AREA = "area"
    RATE = "rate"


@dataclass(frozen=True)
class AttributeMeta:
    """The presentation facts attached to one attribute field."""

    label: str
    group: AttributeGroup
    order: int
    format: AttributeFormat
    unit: Unit | None = None
    display: bool = True
    derived: bool = False
    prominent: bool = False


class AttributeSpec(BaseModel):
    """One attribute as declared: label, group, order, format, unit, and any fixed set
    of values it takes.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    group: AttributeGroup
    order: int
    format: AttributeFormat
    unit: Unit | None = None
    display: bool = True
    derived: bool = False
    prominent: bool = False
    choices: tuple[str, ...] | None = None


class MissingAttributeMeta(TypeError):
    """Raised when an attribute field forgets to declare what it means."""

    def __init__(self, model: type[BaseModel], field: str) -> None:
        super().__init__(f"{model.__name__}.{field} declares no AttributeMeta")
        self.model = model
        self.field = field


class MisdeclaredAttribute(TypeError):
    """Raised when the format a field declares does not match the value it holds."""

    def __init__(self, model: type[BaseModel], field: str, problem: str) -> None:
        super().__init__(f"{model.__name__}.{field} {problem}")
        self.model = model
        self.field = field


def choices_of(annotation: Any) -> tuple[str, ...] | None:
    """Read the vocabulary behind a field, so a page renders it without naming it."""
    for candidate in get_args(annotation) or (annotation,):
        if isinstance(candidate, type) and issubclass(candidate, StrEnum):
            return tuple(member.value for member in candidate)
    return None


def meta_of(entries: Iterable[Any]) -> AttributeMeta | None:
    """The registry entry among whatever a field was annotated with."""
    return next(
        (entry for entry in entries if isinstance(entry, AttributeMeta)),
        None,
    )


def specs_of(model: type[BaseModel]) -> tuple[AttributeSpec, ...]:
    """Read the registry entries off a model, in the order a page shows them."""
    specs = [
        _spec_of(model, name, meta_of(field.metadata), field.annotation)
        for name, field in model.model_fields.items()
    ]
    specs.extend(
        _spec_of(
            model,
            name,
            meta_of(get_args(computed.return_type)),
            computed.return_type,
        )
        for name, computed in model.model_computed_fields.items()
    )
    return tuple(sorted(specs, key=lambda spec: (spec.order, spec.key)))


def computed_keys(model: type[BaseModel]) -> set[str]:
    """The names a model works out rather than records."""
    return set(model.model_computed_fields)


def _spec_of(
    model: type[BaseModel],
    name: str,
    meta: AttributeMeta | None,
    annotation: Any,
) -> AttributeSpec:
    if meta is None:
        raise MissingAttributeMeta(model, name)
    choices = choices_of(annotation)
    if choices is not None and meta.format is not AttributeFormat.ENUM:
        raise MisdeclaredAttribute(
            model, name, "holds a vocabulary but is not declared as an enum"
        )
    if choices is None and meta.format is AttributeFormat.ENUM:
        raise MisdeclaredAttribute(
            model, name, "is declared as an enum but holds no vocabulary"
        )
    if meta.prominent and not meta.display:
        raise MisdeclaredAttribute(model, name, "is prominent but is never displayed")
    return AttributeSpec(
        key=name,
        label=meta.label,
        group=meta.group,
        order=meta.order,
        format=meta.format,
        unit=meta.unit,
        display=meta.display,
        derived=meta.derived,
        prominent=meta.prominent,
        choices=choices,
    )


class SkillRequirement(BaseModel):
    """A skill level something needs before it can be used."""

    model_config = ConfigDict(frozen=True)

    skill: Annotated[Skill, BeforeValidator(Skill.coerce)]
    level: int = Field(ge=1, le=99)


class ItemAttributes(BaseModel):
    """Everything the sources say about an item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tradeable: Annotated[
        bool | None,
        AttributeMeta(
            "Tradeable",
            AttributeGroup.TRADE,
            10,
            AttributeFormat.BOOL,
            prominent=True,
        ),
    ] = None
    ge_buy_limit: Annotated[
        int | None,
        AttributeMeta("Buy limit", AttributeGroup.TRADE, 20, AttributeFormat.INT),
    ] = None
    shop_price: Annotated[
        int | None,
        AttributeMeta(
            "Shop price",
            AttributeGroup.TRADE,
            30,
            AttributeFormat.GP,
            prominent=True,
        ),
    ] = None
    alchemizable: Annotated[
        bool | None,
        AttributeMeta("Alchemizable", AttributeGroup.TRADE, 32, AttributeFormat.BOOL),
    ] = None
    high_alch_value: Annotated[
        int | None,
        AttributeMeta(
            "High alchemy", AttributeGroup.TRADE, 34, AttributeFormat.GP, derived=True
        ),
    ] = None
    low_alch_value: Annotated[
        int | None,
        AttributeMeta(
            "Low alchemy", AttributeGroup.TRADE, 36, AttributeFormat.GP, derived=True
        ),
    ] = None
    lendable: Annotated[
        bool | None,
        AttributeMeta("Lendable", AttributeGroup.TRADE, 40, AttributeFormat.BOOL),
    ] = None
    archery_ticket_price: Annotated[
        int | None,
        AttributeMeta(
            "Archery ticket price", AttributeGroup.TRADE, 50, AttributeFormat.INT
        ),
    ] = None
    tokkul_price: Annotated[
        int | None,
        AttributeMeta("Tokkul price", AttributeGroup.TRADE, 52, AttributeFormat.INT),
    ] = None
    castle_wars_ticket_price: Annotated[
        int | None,
        AttributeMeta(
            "Castle Wars ticket price", AttributeGroup.TRADE, 54, AttributeFormat.INT
        ),
    ] = None
    point_price: Annotated[
        int | None,
        AttributeMeta("Point price", AttributeGroup.TRADE, 56, AttributeFormat.INT),
    ] = None
    weight: Annotated[
        float | None,
        AttributeMeta(
            "Weight",
            AttributeGroup.GENERAL,
            60,
            AttributeFormat.FLOAT,
            unit=Unit.KILOGRAMS,
            prominent=True,
        ),
    ] = None
    bankable: Annotated[
        bool | None,
        AttributeMeta("Bankable", AttributeGroup.GENERAL, 62, AttributeFormat.BOOL),
    ] = None
    rare_item: Annotated[
        bool | None,
        AttributeMeta("Rare item", AttributeGroup.GENERAL, 64, AttributeFormat.BOOL),
    ] = None
    destroy: Annotated[
        bool | None,
        AttributeMeta(
            "Destroyed on drop", AttributeGroup.GENERAL, 70, AttributeFormat.BOOL
        ),
    ] = None
    destroy_message: Annotated[
        str | None,
        AttributeMeta(
            "Destroy option", AttributeGroup.GENERAL, 80, AttributeFormat.TEXT
        ),
    ] = None
    equipment_slot: Annotated[
        EquipmentSlot | None,
        BeforeValidator(EquipmentSlot.coerce),
        AttributeMeta(
            "Equipment slot",
            AttributeGroup.EQUIPMENT,
            90,
            AttributeFormat.ENUM,
            prominent=True,
        ),
    ] = None
    two_handed: Annotated[
        bool | None,
        AttributeMeta("Two-handed", AttributeGroup.EQUIPMENT, 92, AttributeFormat.BOOL),
    ] = None
    attack_speed: Annotated[
        int | None,
        AttributeMeta(
            "Attack speed",
            AttributeGroup.EQUIPMENT,
            100,
            AttributeFormat.INT,
            unit=Unit.TICKS,
        ),
    ] = None
    has_special: Annotated[
        bool | None,
        AttributeMeta(
            "Special attack", AttributeGroup.EQUIPMENT, 110, AttributeFormat.BOOL
        ),
    ] = None
    bonuses: Annotated[
        CombatBonuses | None,
        BeforeValidator(CombatBonuses.coerce),
        AttributeMeta(
            "Combat bonuses", AttributeGroup.EQUIPMENT, 120, AttributeFormat.BONUSES
        ),
    ] = None
    absorb: Annotated[
        AbsorbBonuses | None,
        BeforeValidator(AbsorbBonuses.coerce),
        AttributeMeta(
            "Absorption", AttributeGroup.EQUIPMENT, 130, AttributeFormat.ABSORB
        ),
    ] = None
    requirements: Annotated[
        tuple[SkillRequirement, ...] | None,
        AttributeMeta(
            "Requirements", AttributeGroup.EQUIPMENT, 140, AttributeFormat.SKILLS
        ),
    ] = None
    fun_weapon: Annotated[
        bool | None,
        AttributeMeta(
            "Fun weapon", AttributeGroup.EQUIPMENT, 145, AttributeFormat.BOOL
        ),
    ] = None
    weapon_interface: Annotated[
        int | None,
        AttributeMeta(
            "Weapon interface",
            AttributeGroup.INTERNAL,
            200,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    render_anim: Annotated[
        int | None,
        AttributeMeta(
            "Render animation",
            AttributeGroup.INTERNAL,
            210,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    equip_audio: Annotated[
        int | None,
        AttributeMeta(
            "Equip audio",
            AttributeGroup.INTERNAL,
            220,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    hat: Annotated[
        bool | None,
        AttributeMeta(
            "Hat", AttributeGroup.INTERNAL, 230, AttributeFormat.BOOL, display=False
        ),
    ] = None
    remove_head: Annotated[
        bool | None,
        AttributeMeta(
            "Hides head",
            AttributeGroup.INTERNAL,
            232,
            AttributeFormat.BOOL,
            display=False,
        ),
    ] = None
    remove_sleeves: Annotated[
        bool | None,
        AttributeMeta(
            "Hides sleeves",
            AttributeGroup.INTERNAL,
            234,
            AttributeFormat.BOOL,
            display=False,
        ),
    ] = None
    remove_beard: Annotated[
        bool | None,
        AttributeMeta(
            "Hides beard",
            AttributeGroup.INTERNAL,
            236,
            AttributeFormat.BOOL,
            display=False,
        ),
    ] = None
    attack_anims: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Attack animations",
            AttributeGroup.INTERNAL,
            240,
            AttributeFormat.IDS,
            display=False,
        ),
    ] = None
    defence_anim: Annotated[
        int | None,
        AttributeMeta(
            "Defence animation",
            AttributeGroup.INTERNAL,
            242,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    walk_anim: Annotated[
        int | None,
        AttributeMeta(
            "Walk animation",
            AttributeGroup.INTERNAL,
            244,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    run_anim: Annotated[
        int | None,
        AttributeMeta(
            "Run animation",
            AttributeGroup.INTERNAL,
            246,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    stand_anim: Annotated[
        int | None,
        AttributeMeta(
            "Stand animation",
            AttributeGroup.INTERNAL,
            248,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    stand_turn_anim: Annotated[
        int | None,
        AttributeMeta(
            "Stand-turn animation",
            AttributeGroup.INTERNAL,
            250,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    turn90cw_anim: Annotated[
        int | None,
        AttributeMeta(
            "Turn 90 clockwise",
            AttributeGroup.INTERNAL,
            252,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    turn90ccw_anim: Annotated[
        int | None,
        AttributeMeta(
            "Turn 90 anticlockwise",
            AttributeGroup.INTERNAL,
            254,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    turn180_anim: Annotated[
        int | None,
        AttributeMeta(
            "Turn 180",
            AttributeGroup.INTERNAL,
            256,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    attack_audios: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Attack audio",
            AttributeGroup.INTERNAL,
            258,
            AttributeFormat.IDS,
            display=False,
        ),
    ] = None


class NpcAttributes(BaseModel):
    """Everything the sources say about an npc."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    combat_level: Annotated[
        int | None,
        AttributeMeta(
            "Combat level",
            AttributeGroup.COMBAT,
            5,
            AttributeFormat.INT,
            derived=True,
            prominent=True,
        ),
    ] = None
    lifepoints: Annotated[
        int | None,
        AttributeMeta(
            "Lifepoints",
            AttributeGroup.COMBAT,
            10,
            AttributeFormat.INT,
            prominent=True,
        ),
    ] = None
    attack_level: Annotated[
        int | None,
        AttributeMeta("Attack level", AttributeGroup.COMBAT, 20, AttributeFormat.INT),
    ] = None
    strength_level: Annotated[
        int | None,
        AttributeMeta("Strength level", AttributeGroup.COMBAT, 30, AttributeFormat.INT),
    ] = None
    defence_level: Annotated[
        int | None,
        AttributeMeta("Defence level", AttributeGroup.COMBAT, 40, AttributeFormat.INT),
    ] = None
    magic_level: Annotated[
        int | None,
        AttributeMeta("Magic level", AttributeGroup.COMBAT, 50, AttributeFormat.INT),
    ] = None
    range_level: Annotated[
        int | None,
        AttributeMeta("Ranged level", AttributeGroup.COMBAT, 60, AttributeFormat.INT),
    ] = None
    attack_speed: Annotated[
        int | None,
        AttributeMeta(
            "Attack speed",
            AttributeGroup.COMBAT,
            65,
            AttributeFormat.INT,
            unit=Unit.TICKS,
        ),
    ] = None
    bonuses: Annotated[
        CombatBonuses | None,
        BeforeValidator(CombatBonuses.coerce),
        AttributeMeta(
            "Combat bonuses", AttributeGroup.COMBAT, 70, AttributeFormat.BONUSES
        ),
    ] = None
    combat_style: Annotated[
        CombatStyle | None,
        BeforeValidator(CombatStyle.coerce),
        AttributeMeta(
            "Combat style",
            AttributeGroup.COMBAT,
            75,
            AttributeFormat.ENUM,
            prominent=True,
        ),
    ] = None
    weakness: Annotated[
        int | None,
        AttributeMeta("Weakness", AttributeGroup.COMBAT, 80, AttributeFormat.INT),
    ] = None
    protect_style: Annotated[
        CombatStyle | None,
        BeforeValidator(CombatStyle.coerce),
        AttributeMeta(
            "Protection style", AttributeGroup.COMBAT, 85, AttributeFormat.ENUM
        ),
    ] = None
    slayer_exp: Annotated[
        float | None,
        AttributeMeta(
            "Slayer experience", AttributeGroup.COMBAT, 90, AttributeFormat.FLOAT
        ),
    ] = None
    aggressive: Annotated[
        bool | None,
        AttributeMeta(
            "Aggressive",
            AttributeGroup.BEHAVIOUR,
            100,
            AttributeFormat.BOOL,
            prominent=True,
        ),
    ] = None
    agg_radius: Annotated[
        int | None,
        AttributeMeta(
            "Aggression radius",
            AttributeGroup.BEHAVIOUR,
            110,
            AttributeFormat.INT,
            unit=Unit.TILES,
        ),
    ] = None
    respawn_delay: Annotated[
        int | None,
        AttributeMeta(
            "Respawn delay",
            AttributeGroup.BEHAVIOUR,
            120,
            AttributeFormat.INT,
            unit=Unit.TICKS,
        ),
    ] = None
    safespot: Annotated[
        bool | None,
        AttributeMeta(
            "Safespottable", AttributeGroup.BEHAVIOUR, 130, AttributeFormat.BOOL
        ),
    ] = None
    poisonous: Annotated[
        bool | None,
        AttributeMeta("Poisonous", AttributeGroup.BEHAVIOUR, 132, AttributeFormat.BOOL),
    ] = None
    poison_amount: Annotated[
        int | None,
        AttributeMeta(
            "Poison damage", AttributeGroup.BEHAVIOUR, 134, AttributeFormat.INT
        ),
    ] = None
    poison_immune: Annotated[
        bool | None,
        AttributeMeta(
            "Immune to poison", AttributeGroup.BEHAVIOUR, 136, AttributeFormat.BOOL
        ),
    ] = None
    movement_radius: Annotated[
        int | None,
        AttributeMeta(
            "Movement radius",
            AttributeGroup.BEHAVIOUR,
            138,
            AttributeFormat.INT,
            unit=Unit.TILES,
        ),
    ] = None
    can_tolerate: Annotated[
        bool | None,
        AttributeMeta(
            "Becomes tolerant", AttributeGroup.BEHAVIOUR, 139, AttributeFormat.BOOL
        ),
    ] = None
    clue_level: Annotated[
        ClueLevel | None,
        BeforeValidator(ClueLevel.coerce),
        AttributeMeta(
            "Clue scroll level", AttributeGroup.DROPS, 140, AttributeFormat.ENUM
        ),
    ] = None
    slayer_task: Annotated[
        int | None,
        AttributeMeta("Slayer task", AttributeGroup.DROPS, 145, AttributeFormat.ID),
    ] = None
    combat_audio: Annotated[
        tuple[int, ...] | None,
        AttributeMeta(
            "Combat audio",
            AttributeGroup.INTERNAL,
            200,
            AttributeFormat.IDS,
            display=False,
        ),
    ] = None
    death_animation: Annotated[
        int | None,
        AttributeMeta(
            "Death animation",
            AttributeGroup.INTERNAL,
            210,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    defence_animation: Annotated[
        int | None,
        AttributeMeta(
            "Defence animation",
            AttributeGroup.INTERNAL,
            220,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    melee_animation: Annotated[
        int | None,
        AttributeMeta(
            "Melee animation",
            AttributeGroup.INTERNAL,
            230,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    magic_animation: Annotated[
        int | None,
        AttributeMeta(
            "Magic animation",
            AttributeGroup.INTERNAL,
            240,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    range_animation: Annotated[
        int | None,
        AttributeMeta(
            "Ranged animation",
            AttributeGroup.INTERNAL,
            250,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    spawn_animation: Annotated[
        int | None,
        AttributeMeta(
            "Spawn animation",
            AttributeGroup.INTERNAL,
            260,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    death_gfx: Annotated[
        int | None,
        AttributeMeta(
            "Death graphic",
            AttributeGroup.INTERNAL,
            262,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    start_gfx: Annotated[
        int | None,
        AttributeMeta(
            "Start graphic",
            AttributeGroup.INTERNAL,
            264,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    end_gfx: Annotated[
        int | None,
        AttributeMeta(
            "End graphic",
            AttributeGroup.INTERNAL,
            266,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    projectile: Annotated[
        int | None,
        AttributeMeta(
            "Projectile",
            AttributeGroup.INTERNAL,
            268,
            AttributeFormat.ID,
            display=False,
        ),
    ] = None
    prj_height: Annotated[
        int | None,
        AttributeMeta(
            "Projectile height",
            AttributeGroup.INTERNAL,
            270,
            AttributeFormat.INT,
            display=False,
        ),
    ] = None
    start_height: Annotated[
        int | None,
        AttributeMeta(
            "Start height",
            AttributeGroup.INTERNAL,
            272,
            AttributeFormat.INT,
            display=False,
        ),
    ] = None
    end_height: Annotated[
        int | None,
        AttributeMeta(
            "End height",
            AttributeGroup.INTERNAL,
            274,
            AttributeFormat.INT,
            display=False,
        ),
    ] = None
    spell_id: Annotated[
        int | None,
        AttributeMeta(
            "Spell", AttributeGroup.INTERNAL, 276, AttributeFormat.ID, display=False
        ),
    ] = None
    water_npc: Annotated[
        bool | None,
        AttributeMeta(
            "Lives in water",
            AttributeGroup.INTERNAL,
            278,
            AttributeFormat.BOOL,
            display=False,
        ),
    ] = None
    facing_booth: Annotated[
        bool | None,
        AttributeMeta(
            "Faces a booth",
            AttributeGroup.INTERNAL,
            280,
            AttributeFormat.BOOL,
            display=False,
        ),
    ] = None
    force_talk: Annotated[
        str | None,
        AttributeMeta(
            "Forced dialogue",
            AttributeGroup.INTERNAL,
            282,
            AttributeFormat.TEXT,
            display=False,
        ),
    ] = None


class ShopAttributes(BaseModel):
    """Everything the sources say about a shop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    general_store: Annotated[
        bool | None,
        AttributeMeta(
            "General store",
            AttributeGroup.SHOP,
            10,
            AttributeFormat.BOOL,
            prominent=True,
        ),
    ] = None
    currency: Annotated[
        EntityKey | None,
        BeforeValidator(coerce_item_ref),
        AttributeMeta(
            "Currency",
            AttributeGroup.SHOP,
            20,
            AttributeFormat.REF,
            prominent=True,
        ),
    ] = None
    high_alch: Annotated[
        bool | None,
        AttributeMeta(
            "Buys alchemy products", AttributeGroup.SHOP, 30, AttributeFormat.BOOL
        ),
    ] = None


class QuestAttributes(BaseModel):
    """Everything we record about a quest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    difficulty: Annotated[
        QuestDifficulty | None,
        BeforeValidator(QuestDifficulty.coerce),
        AttributeMeta(
            "Difficulty",
            AttributeGroup.OVERVIEW,
            10,
            AttributeFormat.ENUM,
            prominent=True,
        ),
    ] = None
    length: Annotated[
        QuestLength | None,
        BeforeValidator(QuestLength.coerce),
        AttributeMeta(
            "Length",
            AttributeGroup.OVERVIEW,
            20,
            AttributeFormat.ENUM,
            prominent=True,
        ),
    ] = None
    quest_points: Annotated[
        int | None,
        AttributeMeta(
            "Quest points",
            AttributeGroup.OVERVIEW,
            30,
            AttributeFormat.INT,
            prominent=True,
        ),
    ] = None
    members: Annotated[
        bool | None,
        AttributeMeta(
            "Members only",
            AttributeGroup.OVERVIEW,
            40,
            AttributeFormat.BOOL,
            prominent=True,
        ),
    ] = None
    series: Annotated[
        str | None,
        AttributeMeta("Series", AttributeGroup.OVERVIEW, 50, AttributeFormat.TEXT),
    ] = None


class LocationAttributes(BaseModel):
    """Everything we record about a place on the map."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[
        LocationKind | None,
        BeforeValidator(LocationKind.coerce),
        AttributeMeta(
            "Kind",
            AttributeGroup.OVERVIEW,
            10,
            AttributeFormat.ENUM,
            prominent=True,
        ),
    ] = None
    centre: Annotated[
        Coordinate | None,
        AttributeMeta("Centre", AttributeGroup.MAP, 20, AttributeFormat.COORD),
    ] = None
    bounds: Annotated[
        Area | None,
        AttributeMeta("Extent", AttributeGroup.MAP, 30, AttributeFormat.AREA),
    ] = None
    region_id: Annotated[
        int | None,
        AttributeMeta(
            "Region", AttributeGroup.MAP, 40, AttributeFormat.ID, derived=True
        ),
    ] = None
    members: Annotated[
        bool | None,
        AttributeMeta(
            "Members only",
            AttributeGroup.OVERVIEW,
            50,
            AttributeFormat.BOOL,
            prominent=True,
        ),
    ] = None
    multicombat: Annotated[
        bool | None,
        AttributeMeta("Multicombat", AttributeGroup.OVERVIEW, 60, AttributeFormat.BOOL),
    ] = None
    wilderness_level: Annotated[
        int | None,
        AttributeMeta(
            "Wilderness level",
            AttributeGroup.OVERVIEW,
            70,
            AttributeFormat.INT,
            prominent=True,
        ),
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
    """An attribute set for the given type with nothing filled in."""
    return ATTRIBUTE_MODELS[entity_type]()


# test cases


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


def test_every_vocabulary_field_declares_its_choices() -> None:
    for specs in ATTRIBUTE_SPECS.values():
        for spec in specs:
            if spec.format is AttributeFormat.ENUM:
                assert spec.choices, f"{spec.key} declares no choices"
            else:
                assert spec.choices is None


def test_a_vocabulary_the_front_end_cannot_render_is_rejected() -> None:
    import pytest

    class SaysText(BaseModel):
        kind: Annotated[
            LocationKind | None,
            AttributeMeta("Kind", AttributeGroup.OVERVIEW, 10, AttributeFormat.TEXT),
        ] = None

    class SaysEnum(BaseModel):
        count: Annotated[
            int | None,
            AttributeMeta("Count", AttributeGroup.OVERVIEW, 10, AttributeFormat.ENUM),
        ] = None

    for model in (SaysText, SaysEnum):
        with pytest.raises(MisdeclaredAttribute):
            specs_of(model)


def test_the_choices_carry_the_whole_vocabulary() -> None:
    item_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.ITEM]}
    slot = item_specs["equipment_slot"]
    assert slot.format is AttributeFormat.ENUM
    assert slot.choices is not None
    assert "weapon" in slot.choices
    assert len(slot.choices) == len(list(EquipmentSlot))


def test_a_raw_game_ordinal_becomes_a_named_slot() -> None:
    attributes = ItemAttributes.model_validate({"equipment_slot": 3})
    assert attributes.equipment_slot is EquipmentSlot.WEAPON
    assert attributes.model_dump(exclude_none=True) == {"equipment_slot": "weapon"}


def test_the_clean_name_and_the_raw_ordinal_agree() -> None:
    from_ordinal = ItemAttributes.model_validate({"equipment_slot": 3})
    from_name = ItemAttributes.model_validate({"equipment_slot": "weapon"})
    assert from_ordinal == from_name


def test_packed_bonuses_arrive_as_named_values() -> None:
    packed = "20,29,-2,0,0,0,3,2,1,0,0,25,0,0,0"
    attributes = ItemAttributes.model_validate({"bonuses": packed})
    assert attributes.bonuses is not None
    assert attributes.bonuses.attack_slash == 29
    assert attributes.bonuses.strength == 25


def test_bonuses_survive_a_round_trip_through_json() -> None:
    attributes = ItemAttributes.model_validate({"bonuses": [0] * 14 + [49]})
    restored = ItemAttributes.model_validate_json(
        attributes.model_dump_json(exclude_none=True)
    )
    assert restored == attributes
    assert restored.bonuses is not None
    assert restored.bonuses.ranged_strength == 49


def test_absorption_arrives_as_named_values() -> None:
    attributes = ItemAttributes.model_validate({"absorb": "1,0,1"})
    assert attributes.absorb is not None
    assert attributes.absorb.melee == 1
    assert attributes.absorb.magic == 0


def test_a_requirement_names_its_skill() -> None:
    attributes = ItemAttributes.model_validate(
        {"requirements": [{"skill": 0, "level": 60}, {"skill": "magic", "level": 55}]}
    )
    assert attributes.requirements is not None
    assert attributes.requirements[0].skill is Skill.ATTACK
    assert attributes.requirements[1].skill is Skill.MAGIC


def test_npc_styles_and_clue_tiers_come_back_named() -> None:
    attributes = NpcAttributes.model_validate(
        {"combat_style": 1, "protect_style": 2, "clue_level": 2}
    )
    assert attributes.combat_style is CombatStyle.RANGE
    assert attributes.protect_style is CombatStyle.MAGIC
    assert attributes.clue_level is ClueLevel.HARD


def test_an_npc_weakness_stays_the_opaque_number_the_server_uses() -> None:
    npc_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.NPC]}
    assert npc_specs["weakness"].format is AttributeFormat.INT
    assert npc_specs["weakness"].choices is None


def test_a_shop_currency_is_an_item_reference_not_a_number() -> None:
    attributes = ShopAttributes.model_validate({"currency": 995})
    assert attributes.currency == COINS
    assert ShopAttributes.model_validate({"currency": "item:995"}).currency == COINS


def test_quest_difficulty_and_length_are_closed_vocabularies() -> None:
    import pytest

    attributes = QuestAttributes.model_validate(
        {"difficulty": "Novice", "length": "Short"}
    )
    assert attributes.difficulty is QuestDifficulty.NOVICE
    assert attributes.length is QuestLength.SHORT
    with pytest.raises(ValueError):
        QuestAttributes.model_validate({"difficulty": "quite hard actually"})


def test_a_quest_start_point_is_a_relationship_not_an_attribute() -> None:
    assert "start_location" not in QuestAttributes.model_fields


def test_units_are_declared_from_a_closed_set() -> None:
    item_specs = {spec.key: spec for spec in ATTRIBUTE_SPECS[EntityType.ITEM]}
    assert item_specs["weight"].unit is Unit.KILOGRAMS
    assert item_specs["attack_speed"].unit is Unit.TICKS
    assert item_specs["ge_buy_limit"].unit is None


def test_groups_are_declared_from_a_closed_set() -> None:
    for specs in ATTRIBUTE_SPECS.values():
        assert all(isinstance(spec.group, AttributeGroup) for spec in specs)


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


def test_every_type_declares_something_worth_showing_on_hover() -> None:
    for entity_type, specs in ATTRIBUTE_SPECS.items():
        prominent = [spec for spec in specs if spec.prominent]
        assert prominent, f"{entity_type.value} declares no prominent attribute"


def test_a_tooltip_stays_small_enough_to_hover_over() -> None:
    for specs in ATTRIBUTE_SPECS.values():
        assert len([spec for spec in specs if spec.prominent]) <= 5


def test_a_prominent_attribute_is_one_the_reader_can_see() -> None:
    import pytest

    class Invisible(BaseModel):
        secret: Annotated[
            int | None,
            AttributeMeta(
                "Secret",
                AttributeGroup.INTERNAL,
                10,
                AttributeFormat.INT,
                display=False,
                prominent=True,
            ),
        ] = None

    with pytest.raises(MisdeclaredAttribute):
        specs_of(Invisible)


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
