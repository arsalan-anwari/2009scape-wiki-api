"""The sources staging is allowed to read, listed one line each."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

GAME_REPO: Final = "2009scape"
GAME_CHECKOUT: Final = "2009scape"
CONFIG_ROOT: Final = "Server/data/configs"
CODE_ROOT: Final = "Server/src/main"
CONFIGS_DIRECTORY: Final = "configs"
TABLES_DIRECTORY: Final = "tables"
PRICES_DIRECTORY: Final = "grand-exchange"


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


def test_no_source_is_declared_twice() -> None:
    names = [declared.staged for declared in DECLARED_CONFIGS]
    enums = [declared.staged for declared in DECLARED_TABLES]
    assert len(set(names)) == len(names)
    assert len(set(enums)) == len(enums)


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
