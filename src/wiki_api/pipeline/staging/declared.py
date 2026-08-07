"""The sources staging is allowed to read, listed one line each."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

GAME_REPO: Final = "2009scape"
GAME_CHECKOUT: Final = "2009scape"
CONFIG_ROOT: Final = "Server/data/configs"
CODE_ROOT: Final = "Server/src/main"
CACHE_ROOT: Final = "Server/data/cache"
CONFIGS_DIRECTORY: Final = "configs"
TABLES_DIRECTORY: Final = "tables"
PRICES_DIRECTORY: Final = "grand-exchange"
CACHE_DIRECTORY: Final = "cache"


class DeclaredConfig(BaseModel):
    """One config file staging copies across unchanged."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return f"{CONFIG_ROOT}/{self.name}"

    @property
    def staged(self) -> str:
        return f"{CONFIGS_DIRECTORY}/{self.name}"


class DeclaredTable(BaseModel):
    """One enum staging reads out of the game's code as a table."""

    model_config = ConfigDict(frozen=True)

    enum: str = Field(min_length=1)
    path: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return f"{CODE_ROOT}/{self.path}"

    @property
    def staged(self) -> str:
        return f"{TABLES_DIRECTORY}/{self.enum}.json"

    @property
    def filename(self) -> str:
        return self.path.rsplit("/", 1)[-1]


class DeclaredExtract(BaseModel):
    """One table staging decodes out of the game cache."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    index: int = Field(ge=0)
    compressed: bool = False

    @property
    def upstream(self) -> str:
        return CACHE_ROOT

    @property
    def staged(self) -> str:
        suffix = ".jsonl.gz" if self.compressed else ".json"
        return f"{CACHE_DIRECTORY}/{self.name}{suffix}"


DECLARED_CONFIGS: Final[tuple[DeclaredConfig, ...]] = (
    DeclaredConfig(name="item_configs.json"),
    DeclaredConfig(name="npc_configs.json"),
    DeclaredConfig(name="shops.json"),
    DeclaredConfig(name="drop_tables.json"),
    DeclaredConfig(name="npc_spawns.json"),
    DeclaredConfig(name="ground_spawns.json"),
    DeclaredConfig(name="ranged_weapon_configs.json"),
    DeclaredConfig(name="ammo_configs.json"),
    DeclaredConfig(name="object_configs.json"),
    DeclaredConfig(name="music_regions.json"),
    DeclaredConfig(name="clue_rewards.json"),
    DeclaredConfig(name="xteas.json"),
)

ITEM_EXTRACT: Final = DeclaredExtract(name="items", index=19)
SCENERY_EXTRACT: Final = DeclaredExtract(name="scenery", index=16)
NPC_EXTRACT: Final = DeclaredExtract(name="npcs", index=18)
PLACEMENT_EXTRACT: Final = DeclaredExtract(name="placements", index=5, compressed=True)

DECLARED_EXTRACTS: Final[tuple[DeclaredExtract, ...]] = (
    ITEM_EXTRACT,
    SCENERY_EXTRACT,
    NPC_EXTRACT,
    PLACEMENT_EXTRACT,
)

DECLARED_TABLES: Final[tuple[DeclaredTable, ...]] = (
    DeclaredTable(enum="Quests", path="content/data/Quests.kt"),
    DeclaredTable(
        enum="SkillingResource",
        path="content/global/skill/gather/SkillingResource.java",
    ),
    DeclaredTable(
        enum="CookableItems",
        path="content/global/skill/cooking/CookableItems.java",
    ),
    DeclaredTable(enum="Bars", path="content/global/skill/smithing/Bars.java"),
    DeclaredTable(enum="Tasks", path="content/global/skill/slayer/Tasks.java"),
    DeclaredTable(enum="Master", path="content/global/skill/slayer/Master.java"),
    DeclaredTable(enum="Fish", path="content/global/skill/fishing/Fish.kt"),
    DeclaredTable(enum="SkillingTool", path="content/data/skill/SkillingTool.java"),
    DeclaredTable(
        enum="SummoningScroll",
        path="content/global/skill/summoning/SummoningScroll.java",
    ),
    DeclaredTable(
        enum="RoomProperties",
        path="content/global/skill/construction/RoomProperties.java",
    ),
    DeclaredTable(enum="Stall", path="content/global/skill/thieving/Stall.java"),
)


# test cases


def test_a_declared_config_knows_both_ends_of_the_copy() -> None:
    declared = DeclaredConfig(name="item_configs.json")
    assert declared.upstream == "Server/data/configs/item_configs.json"
    assert declared.staged == "configs/item_configs.json"


def test_a_declared_table_lands_under_its_enum_name() -> None:
    declared = DeclaredTable(enum="Quests", path="content/data/Quests.kt")
    assert declared.upstream == "Server/src/main/content/data/Quests.kt"
    assert declared.staged == "tables/Quests.json"
    assert declared.filename == "Quests.kt"


def test_a_declared_extract_lands_under_the_cache_it_was_decoded_from() -> None:
    assert ITEM_EXTRACT.staged == "cache/items.json"
    assert PLACEMENT_EXTRACT.staged == "cache/placements.jsonl.gz"
    assert ITEM_EXTRACT.upstream == "Server/data/cache"


def test_no_source_is_declared_twice() -> None:
    names = [declared.staged for declared in DECLARED_CONFIGS]
    enums = [declared.staged for declared in DECLARED_TABLES]
    extracts = [declared.staged for declared in DECLARED_EXTRACTS]
    assert len(set(names)) == len(names)
    assert len(set(enums)) == len(enums)
    assert len(set(extracts)) == len(extracts)


def test_the_keys_the_map_decode_needs_are_staged() -> None:
    assert "xteas.json" in {declared.name for declared in DECLARED_CONFIGS}


def test_the_sources_the_adapters_read_are_all_declared() -> None:
    staged = {declared.name for declared in DECLARED_CONFIGS}
    assert {
        "item_configs.json",
        "npc_configs.json",
        "shops.json",
        "drop_tables.json",
        "npc_spawns.json",
        "ranged_weapon_configs.json",
    } <= staged
    assert "Quests" in {declared.enum for declared in DECLARED_TABLES}
