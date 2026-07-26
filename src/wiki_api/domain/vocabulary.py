"""The closed sets of names this knowledge base speaks.

The game sources ship everything as text, so each type here accepts the raw form
on the way in and stores one clean name. Every vocabulary cites the server file
it was checked against.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Self

from pydantic import BaseModel, ConfigDict

from wiki_api.domain.identity import EntityKey, EntityType

if TYPE_CHECKING:
    from collections.abc import Sequence


class GameEnum(StrEnum):
    """A vocabulary that takes the spelling the game uses and stores a clean name."""

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
    """The 24 skills, in the id order the server uses.

    Checked against Server/src/main/core/game/node/entity/skill/Skills.java.
    """

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
    """Where an item is worn.

    Checked against Server/src/main/core/api/EquipmentSlot.kt. The hidden slots are real
    positions in that enum, so removing them would shift every slot after them.
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
    """How an npc fights, and which prayer protects against it.

    Checked against Server/src/main/core/game/node/entity/combat/CombatStyle.java.
    """

    MELEE = "melee"
    RANGE = "range"
    MAGIC = "magic"


class ClueLevel(OrdinalEnum):
    """The clue scroll tier an npc drops.

    Checked against Server/src/main/content/global/activity/ttrail/ClueLevel.java.
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"


class QuestDifficulty(GameEnum):
    """How hard a quest is.

    Quests.kt carries only the name, so this vocabulary is ours rather than the
    game's.
    """

    NOVICE = "novice"
    INTERMEDIATE = "intermediate"
    EXPERIENCED = "experienced"
    MASTER = "master"
    GRANDMASTER = "grandmaster"
    SPECIAL = "special"


class QuestLength(GameEnum):
    """Roughly how long a quest takes.

    Another vocabulary of ours rather than the game's.
    """

    VERY_SHORT = "very_short"
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    VERY_LONG = "very_long"


class AttributeGroup(GameEnum):
    """Which section of a page an attribute belongs in."""

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
    INTERNAL = "internal"


class RelationshipGroup(GameEnum):
    """Which section of a page the rows of a relationship belong in."""

    DROPS = "drops"
    TRADE = "trade"
    QUESTS = "quests"
    EQUIPMENT = "equipment"
    MAP = "map"


class Unit(GameEnum):
    """The unit a numeric attribute is measured in."""

    KILOGRAMS = "kg"
    TICKS = "ticks"
    TILES = "tiles"


class HiddenReason(GameEnum):
    """Why an entity is in the artifact but not served to readers."""

    UNNAMED = "unnamed"
    SUPPRESSED = "suppressed"
    DUPLICATE = "duplicate"
    PLACEHOLDER = "placeholder"


class SourceKind(GameEnum):
    """What sort of upstream a fact was derived from."""

    GAME_CONFIG = "game_config"
    GAME_CODE = "game_code"
    GRAND_EXCHANGE = "grand_exchange"
    OVERLAY = "overlay"
    FIXTURE = "fixture"


def _split_packed(values: str | Sequence[int]) -> tuple[int, ...]:
    if isinstance(values, str):
        return tuple(int(part) for part in values.split(","))
    return tuple(int(part) for part in values)


class PackedInts(BaseModel):
    """A run of ints of fixed width that the sources ship as one comma joined string.

    The order the fields are declared in is the packed order, so the model itself
    says what each position means.
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


class CombatBonuses(PackedInts):
    """The 15 combat bonuses in the order item_configs.json packs them.

    The last two positions carry real values even though the equipment interface
    does not label them.
    """

    attack_stab: int = 0
    attack_slash: int = 0
    attack_crush: int = 0
    attack_magic: int = 0
    attack_ranged: int = 0
    defence_stab: int = 0
    defence_slash: int = 0
    defence_crush: int = 0
    defence_magic: int = 0
    defence_ranged: int = 0
    defence_summoning: int = 0
    strength: int = 0
    prayer: int = 0
    magic_damage: int = 0
    ranged_strength: int = 0


class AbsorbBonuses(PackedInts):
    """The three absorption values."""

    melee: int = 0
    magic: int = 0
    ranged: int = 0


COINS: Final = EntityKey(type=EntityType.ITEM, id=995)

BONUS_WIDTH: Final = 15


def coerce_item_ref(value: Any) -> Any:
    """Accept the bare item id the sources use wherever an item is referenced."""
    if isinstance(value, EntityKey | dict | bool):
        return value
    if isinstance(value, int):
        return EntityKey(type=EntityType.ITEM, id=value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return EntityKey(type=EntityType.ITEM, id=int(text))
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
