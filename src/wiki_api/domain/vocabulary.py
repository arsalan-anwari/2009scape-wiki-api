"""Declare the closed sets of names this knowledge base speaks, each taking the raw
form the sources ship and storing one clean name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict

from wiki_api.domain.identity import EntityKey, EntityType

if TYPE_CHECKING:
    from collections.abc import Sequence


class GameEnum(StrEnum):
    """A vocabulary taking the spelling the game uses, storing a clean name."""

    @classmethod
    def coerce(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        folded = text.lower().replace(" ", "_").replace("-", "_")
        for member in cls:
            if folded in (member.value, member.name.lower()):
                return member
        return value


class OrdinalEnum(GameEnum):
    """A vocabulary the sources write as a position in a server side enum."""

    @property
    def ordinal(self) -> int:
        return list(type(self)).index(self)

    @classmethod
    def from_ordinal(cls, ordinal: int) -> Self:
        members = list(cls)
        if not 0 <= ordinal < len(members):
            raise ValueError(f"{cls.__name__} has no member at ordinal {ordinal}")
        return members[ordinal]

    @classmethod
    def coerce(cls, value: Any) -> Any:
        if isinstance(value, cls | bool):
            return value
        if isinstance(value, int):
            return cls.from_ordinal(value)
        if isinstance(value, str):
            text = value.strip()
            if text.lstrip("-").isdigit():
                return cls.from_ordinal(int(text))
        return super().coerce(value)


class Skill(OrdinalEnum):
    """The 24 skills, in the id order Skills.java uses."""

    ATTACK = "attack"
    DEFENCE = "defence"
    STRENGTH = "strength"
    HITPOINTS = "hitpoints"
    RANGED = "ranged"
    PRAYER = "prayer"
    MAGIC = "magic"
    COOKING = "cooking"
    WOODCUTTING = "woodcutting"
    FLETCHING = "fletching"
    FISHING = "fishing"
    FIREMAKING = "firemaking"
    CRAFTING = "crafting"
    SMITHING = "smithing"
    MINING = "mining"
    HERBLORE = "herblore"
    AGILITY = "agility"
    THIEVING = "thieving"
    SLAYER = "slayer"
    FARMING = "farming"
    RUNECRAFTING = "runecrafting"
    HUNTER = "hunter"
    CONSTRUCTION = "construction"
    SUMMONING = "summoning"


class EquipmentSlot(OrdinalEnum):
    """Where an item is worn, in the order EquipmentSlot.kt declares, hidden slots
    included so nothing after them shifts.
    """

    HEAD = "head"
    CAPE = "cape"
    NECK = "neck"
    WEAPON = "weapon"
    CHEST = "chest"
    SHIELD = "shield"
    HIDDEN_1 = "hidden_1"
    LEGS = "legs"
    HIDDEN_2 = "hidden_2"
    HANDS = "hands"
    FEET = "feet"
    HIDDEN_3 = "hidden_3"
    RING = "ring"
    AMMO = "ammo"


class CombatStyle(OrdinalEnum):
    """How an npc fights, and which prayer protects against it, as CombatStyle.java
    declares.
    """

    MELEE = "melee"
    RANGE = "range"
    MAGIC = "magic"


class ClueLevel(OrdinalEnum):
    """The clue scroll tier an npc drops, as ClueLevel.java declares."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"


class SharedDropTable(GameEnum):
    """A weighted table many drop lists roll on, held apart from any one of them."""

    RARE = "rare"
    GEM = "gem"
    HERB = "herb"
    UNCOMMON_SEED = "uncommon_seed"
    RARE_SEED = "rare_seed"
    ALLOTMENT_SEED = "allotment_seed"
    CELE_MINOR = "cele_minor"


class QuestDifficulty(GameEnum):
    """How hard a quest is, in a vocabulary of ours rather than the game's."""

    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERIENCED = "experienced"
    MASTER = "master"
    GRANDMASTER = "grandmaster"
    SPECIAL = "special"


class QuestLength(GameEnum):
    """How long a quest takes, in a vocabulary of ours rather than the game's."""

    VERY_SHORT = "very_short"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_LONG = "very_long"


class PriceConfidence(GameEnum):
    """How far a recorded price is worth believing, judged by how its record moved."""

    TRADED = "traded"
    STATIC = "static"
    UNTRADED = "untraded"


class WeaponType(OrdinalEnum):
    """What sort of weapon an item is, in the order the game's own list declares them.

    The member names are the game's, and a build refuses to run when the two disagree.
    """

    UNARMED = "unarmed"
    STAFF = "staff"
    AXE = "battleaxe"
    SCEPTER = "scepter"
    PICKAXE = "pickaxe"
    SWORD_DAGGER = "sword_or_dagger"
    SCIMITAR = "scimitar"
    TWO_H_SWORD = "two_handed_sword"
    MACE = "mace"
    CLAWS = "claws"
    WARHAMMER_MAUL = "warhammer_or_maul"
    WHIP = "whip"
    FLOWERS = "flowers"
    MUD_PIE = "mud_pie"
    SPEAR = "spear"
    HALBERD = "halberd"
    BOW = "bow"
    CROSSBOW = "crossbow"
    THROWN_WEAPONS = "thrown"
    CHINCHOMPA = "chinchompa"
    FIXED_DEVICE = "fixed_device"
    SALAMANDER = "salamander"
    SCYTHE = "scythe"
    IVANDIS_FLAIL = "flail"


class AttributeGroup(GameEnum):
    """Which part of a page an attribute belongs to, such as the overview box."""

    OVERVIEW = "overview"
    GENERAL = "general"
    TRADE = "trade"
    EQUIPMENT = "equipment"
    COMBAT = "combat"
    BEHAVIOUR = "behaviour"
    DROPS = "drops"
    MAP = "map"
    SHOP = "shop"
    RATE = "rate"
    AMOUNT = "amount"
    REWARD = "reward"
    SKILL = "skill"
    SLAYER = "slayer"
    INTERNAL = "internal"


class RelationshipGroup(GameEnum):
    """Which part of a page the related entities of a relationship belong to."""

    DROPS = "drops"
    TRADE = "trade"
    QUESTS = "quests"
    EQUIPMENT = "equipment"
    MAP = "map"
    SKILL = "skill"
    SLAYER = "slayer"
    PREREQUISITES = "prerequisites"


class Unit(GameEnum):
    """What a numeric value is measured in, such as kilograms or game ticks."""

    KILOGRAMS = "kg"
    TICKS = "ticks"
    TILES = "tiles"


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
    TEXTS = "texts"


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
    #: Whether this value addresses the game rather than describing it.
    technical: bool = False
    #:Whether this value is a count of the world that adds up across namesakes.
    totalled: bool = False


class HiddenReason(GameEnum):
    """Why an entity is kept in the build but not served to readers."""

    UNNAMED = "unnamed"
    SUPPRESSED = "suppressed"
    DUPLICATE = "duplicate"
    PLACEHOLDER = "placeholder"


class SourceKind(GameEnum):
    """What sort of upstream a fact was derived from."""

    GAME_CONFIG = "game_config"
    GAME_CODE = "game_code"
    GAME_CACHE = "game_cache"
    GRAND_EXCHANGE = "grand_exchange"
    OVERLAY = "overlay"
    FIXTURE = "fixture"


def _split_packed(values: str | Sequence[int]) -> tuple[int, ...]:
    if isinstance(values, str):
        return tuple(int(part) for part in values.split(","))
    return tuple(int(part) for part in values)


class PackedInts(BaseModel):
    """A fixed-width run of ints the sources ship as one comma joined string, in the
    order the fields are declared.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    @classmethod
    def from_packed(cls, values: str | Sequence[int]) -> Self:
        parts = _split_packed(values)
        names = tuple(cls.model_fields)
        if len(parts) != len(names):
            raise ValueError(
                f"{cls.__name__} needs {len(names)} values, got {len(parts)}"
            )
        return cls.model_validate(dict(zip(names, parts, strict=True)))

    @classmethod
    def coerce(cls, value: Any) -> Any:
        if isinstance(value, cls | dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            return cls.from_packed(text) if text else None
        if isinstance(value, list | tuple):
            return cls.from_packed(value)
        return value

    @property
    def is_empty(self) -> bool:
        return not any(getattr(self, name) for name in type(self).model_fields)


def _bonus(label: str, order: int) -> AttributeMeta:
    return AttributeMeta(label, AttributeGroup.EQUIPMENT, order, AttributeFormat.INT)


class CombatBonuses(PackedInts):
    """The 15 combat bonuses in the order item_configs.json packs them."""

    attack_stab: Annotated[int, _bonus("Stab attack bonus", 10)] = 0
    attack_slash: Annotated[int, _bonus("Slash attack bonus", 20)] = 0
    attack_crush: Annotated[int, _bonus("Crush attack bonus", 30)] = 0
    attack_magic: Annotated[int, _bonus("Magic attack bonus", 40)] = 0
    attack_ranged: Annotated[int, _bonus("Ranged attack bonus", 50)] = 0
    defence_stab: Annotated[int, _bonus("Stab defence bonus", 60)] = 0
    defence_slash: Annotated[int, _bonus("Slash defence bonus", 70)] = 0
    defence_crush: Annotated[int, _bonus("Crush defence bonus", 80)] = 0
    defence_magic: Annotated[int, _bonus("Magic defence bonus", 90)] = 0
    defence_ranged: Annotated[int, _bonus("Ranged defence bonus", 100)] = 0
    defence_summoning: Annotated[int, _bonus("Summoning defence bonus", 110)] = 0
    strength: Annotated[int, _bonus("Strength bonus", 120)] = 0
    prayer: Annotated[int, _bonus("Prayer bonus", 130)] = 0
    magic_damage: Annotated[int, _bonus("Magic damage bonus", 140)] = 0
    ranged_strength: Annotated[int, _bonus("Ranged strength bonus", 150)] = 0


class AbsorbBonuses(PackedInts):
    """The three absorption values."""

    melee: Annotated[int, _bonus("Melee absorption", 10)] = 0
    magic: Annotated[int, _bonus("Magic absorption", 20)] = 0
    ranged: Annotated[int, _bonus("Ranged absorption", 30)] = 0


COINS: Final = EntityKey(type=EntityType.ITEM, id=995)

BONUS_WIDTH: Final = 15


def coerce_item_ref(value: Any) -> Any:
    """Accept the bare item id the sources use wherever an item is referenced."""
    return _coerce_ref(value, EntityType.ITEM)


def coerce_npc_ref(value: Any) -> Any:
    """Accept the bare npc id the sources use wherever a person is referenced."""
    return _coerce_ref(value, EntityType.NPC)


def _coerce_ref(value: Any, sort: EntityType) -> Any:
    """Read a reference written whichever way its source happened to write it."""
    if isinstance(value, EntityKey | dict | bool):
        return value
    if isinstance(value, int):
        return EntityKey(type=sort, id=value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return EntityKey(type=sort, id=int(text))
        return EntityKey.parse(text)
    return value


# test cases


def test_skill_ids_match_the_servers_own_order() -> None:
    assert Skill.ATTACK.ordinal == 0
    assert Skill.RANGED.ordinal == 4
    assert Skill.MAGIC.ordinal == 6
    assert Skill.SUMMONING.ordinal == 23
    assert len(list(Skill)) == 24


def test_a_raw_ordinal_and_a_clean_name_reach_the_same_member() -> None:
    assert EquipmentSlot.coerce(3) is EquipmentSlot.WEAPON
    assert EquipmentSlot.coerce("3") is EquipmentSlot.WEAPON
    assert EquipmentSlot.coerce("weapon") is EquipmentSlot.WEAPON
    assert EquipmentSlot.coerce(EquipmentSlot.WEAPON) is EquipmentSlot.WEAPON


def test_the_hidden_slots_keep_the_later_ordinals_honest() -> None:
    assert EquipmentSlot.coerce(7) is EquipmentSlot.LEGS
    assert EquipmentSlot.coerce(13) is EquipmentSlot.AMMO
    assert len(list(EquipmentSlot)) == 14


def test_an_empty_source_value_reads_as_missing() -> None:
    assert EquipmentSlot.coerce("") is None
    assert EquipmentSlot.coerce("   ") is None
    assert QuestDifficulty.coerce("") is None


def test_a_name_is_matched_however_the_author_spaced_it() -> None:
    assert QuestLength.coerce("Very Short") is QuestLength.VERY_SHORT
    assert QuestLength.coerce("very-short") is QuestLength.VERY_SHORT
    assert QuestDifficulty.coerce("Novice") is QuestDifficulty.NOVICE


def test_an_unknown_name_is_handed_back_for_pydantic_to_report() -> None:
    assert EquipmentSlot.coerce("banana") == "banana"


def test_an_ordinal_outside_the_vocabulary_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        CombatStyle.from_ordinal(9)
    with pytest.raises(ValueError):
        EquipmentSlot.coerce(99)


def test_combat_and_protect_styles_share_the_servers_enum() -> None:
    assert CombatStyle.coerce(0) is CombatStyle.MELEE
    assert CombatStyle.coerce(1) is CombatStyle.RANGE
    assert CombatStyle.coerce(2) is CombatStyle.MAGIC


def test_clue_levels_follow_the_server_ordinals() -> None:
    assert ClueLevel.coerce(0) is ClueLevel.EASY
    assert ClueLevel.coerce(2) is ClueLevel.HARD


def test_bonuses_unpack_from_the_string_the_sources_ship() -> None:
    packed = "20,29,-2,0,0,0,3,2,1,0,0,25,0,0,0"
    bonuses = CombatBonuses.from_packed(packed)
    assert bonuses.attack_stab == 20
    assert bonuses.attack_slash == 29
    assert bonuses.attack_crush == -2
    assert bonuses.strength == 25
    assert bonuses.ranged_strength == 0


def test_a_packed_string_and_a_list_agree() -> None:
    packed = "0,0,0,0,0,0,0,0,0,0,0,0,0,0,49"
    listed = [0] * 14 + [49]
    assert CombatBonuses.coerce(packed) == CombatBonuses.coerce(listed)


def test_ranged_ammunition_carries_its_strength_at_the_last_index() -> None:
    rune_arrow = CombatBonuses.from_packed("0,0,0,0,0,0,0,0,0,0,0,0,0,0,49")
    assert rune_arrow.ranged_strength == 49
    assert rune_arrow.attack_ranged == 0


def test_the_declared_order_is_the_packed_order() -> None:
    assert tuple(CombatBonuses.model_fields)[:5] == (
        "attack_stab",
        "attack_slash",
        "attack_crush",
        "attack_magic",
        "attack_ranged",
    )
    assert len(CombatBonuses.model_fields) == BONUS_WIDTH


def test_a_run_of_the_wrong_width_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        CombatBonuses.from_packed("1,2,3")
    with pytest.raises(ValueError):
        AbsorbBonuses.from_packed([1, 2, 3, 4])


def test_absorption_reads_melee_magic_ranged() -> None:
    platelegs = AbsorbBonuses.from_packed("1,0,1")
    assert (platelegs.melee, platelegs.magic, platelegs.ranged) == (1, 0, 1)


def test_an_all_zero_run_is_recognised_as_empty() -> None:
    assert CombatBonuses.from_packed([0] * BONUS_WIDTH).is_empty is True
    assert AbsorbBonuses.from_packed("1,0,1").is_empty is False


def test_packed_values_are_frozen_and_closed() -> None:
    import pytest

    bonuses = AbsorbBonuses(melee=1, magic=0, ranged=1)
    frozen_field = "melee"
    with pytest.raises(ValueError):
        setattr(bonuses, frozen_field, 2)
    with pytest.raises(ValueError):
        AbsorbBonuses.model_validate({"melee": 1, "slash": 2})


def test_coins_are_named_rather_than_written_as_995() -> None:
    assert COINS.type is EntityType.ITEM
    assert COINS.id == 995
