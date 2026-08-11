"""The sources staging is allowed to read, listed one line each."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

GAME_REPO: Final = "2009scape"
GAME_CHECKOUT: Final = "2009scape"
CONSTANTS_REPO: Final = "rs09-constants-library"
CONSTANTS_CHECKOUT: Final = "rs09-constants-library"
CONSTANTS_ROOT: Final = "src/main/kotlin/org/rs09/consts"
WIKI_REPO: Final = "2009scape-wiki-website"
WIKI_CHECKOUT: Final = "2009scape-wiki-website"
ANCHORS_REPO: Final = "2009scape-telecoordinates"
ANCHORS_CHECKOUT: Final = "2009scape-telecoordinates"
CONFIG_ROOT: Final = "Server/data/configs"
CODE_ROOT: Final = "Server/src/main"
CACHE_ROOT: Final = "Server/data/cache"
DUMP_ROOT: Final = "dumps/530"
CONFIGS_DIRECTORY: Final = "configs"
TABLES_DIRECTORY: Final = "tables"
CACHE_DIRECTORY: Final = "cache"
CONSTANTS_DIRECTORY: Final = "constants"
CODE_DIRECTORY: Final = "code"
WIKI_DIRECTORY: Final = "wiki"
PLACES_DIRECTORY: Final = "places"


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


class DeclaredConstants(BaseModel):
    """One object of named ids staging reads out of the constants library."""

    model_config = ConfigDict(frozen=True)

    object_name: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return f"{CONSTANTS_ROOT}/{self.object_name}.kt"

    @property
    def staged(self) -> str:
        return f"{CONSTANTS_DIRECTORY}/{self.object_name}.json"

    @property
    def filename(self) -> str:
        return f"{self.object_name}.kt"


class DeclaredScan(BaseModel):
    """One sweep of the game's code for what a class hands its base class."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    root: str = Field(min_length=1)
    base: str = Field(min_length=1)
    qualifier: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return f"{CODE_ROOT}/{self.root}"

    @property
    def staged(self) -> str:
        return f"{CODE_DIRECTORY}/{self.name}.json"

    @property
    def filename(self) -> str:
        return f"{self.base}.java"


class DeclaredPages(BaseModel):
    """One namespace of saved community wiki pages staging reads into sections."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    namespace: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return WIKI_CHECKOUT

    @property
    def staged(self) -> str:
        return f"{WIKI_DIRECTORY}/{self.name}.json"

    @property
    def filename(self) -> str:
        return f"{self.namespace}"


class DeclaredTracks(BaseModel):
    """The dump saying where each music track unlocks, in a sentence a person wrote."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    dump: str = Field(min_length=1)
    partition: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return f"{DUMP_ROOT}/{self.dump}"

    @property
    def staged(self) -> str:
        return f"{PLACES_DIRECTORY}/{self.name}.json"

    @property
    def config(self) -> DeclaredConfig:
        """The already staged config keying a region to the track that plays in it."""
        return DeclaredConfig(name=self.partition)


class DeclaredAnchors(BaseModel):
    """The community's teleport list, which names a point rather than an extent."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)

    @property
    def upstream(self) -> str:
        return self.file

    @property
    def staged(self) -> str:
        return f"{PLACES_DIRECTORY}/{self.name}.json"


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
DATAMAP_EXTRACT: Final = DeclaredExtract(name="datamaps", index=17)
MAP_LABEL_EXTRACT: Final = DeclaredExtract(name="maplabels", index=23)

DECLARED_EXTRACTS: Final[tuple[DeclaredExtract, ...]] = (
    ITEM_EXTRACT,
    SCENERY_EXTRACT,
    NPC_EXTRACT,
    DATAMAP_EXTRACT,
    MAP_LABEL_EXTRACT,
    PLACEMENT_EXTRACT,
)

DECLARED_CONSTANTS: Final[tuple[DeclaredConstants, ...]] = (
    DeclaredConstants(object_name="Items"),
    DeclaredConstants(object_name="NPCs"),
    DeclaredConstants(object_name="Scenery"),
)

QUEST_SCAN: Final = DeclaredScan(
    name="quests", root="content", base="Quest", qualifier="Quests"
)

DECLARED_SCANS: Final[tuple[DeclaredScan, ...]] = (QUEST_SCAN,)

QUEST_PAGES: Final = DeclaredPages(name="quests", namespace="quest_guides")

DECLARED_PAGES: Final[tuple[DeclaredPages, ...]] = (QUEST_PAGES,)

MUSIC_TRACKS: Final = DeclaredTracks(
    name="tracks",
    dump="music_location_unlocks.txt",
    partition="music_regions.json",
)

TELEPORT_ANCHORS: Final = DeclaredAnchors(name="anchors", file="locations.txt")

WEAPON_TYPES: Final = DeclaredTable(
    enum="WeaponInterfaces",
    path="core/game/node/entity/combat/equipment/WeaponInterface.java",
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
    DeclaredTable(enum="BarType", path="content/global/skill/smithing/BarType.java"),
    DeclaredTable(
        enum="SmithingType", path="content/global/skill/smithing/SmithingType.java"
    ),
    DeclaredTable(
        enum="FishingSpot", path="content/global/skill/fishing/FishingSpot.kt"
    ),
    DeclaredTable(
        enum="FishingOption", path="content/global/skill/fishing/FishingOption.kt"
    ),
    DeclaredTable(enum="Consumables", path="content/data/consumables/Consumables.java"),
    WEAPON_TYPES,
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


def test_the_track_dump_stages_on_its_own_and_names_the_config_it_joins() -> None:
    assert MUSIC_TRACKS.upstream == "dumps/530/music_location_unlocks.txt"
    assert MUSIC_TRACKS.staged == "places/tracks.json"
    assert MUSIC_TRACKS.config.staged == "configs/music_regions.json"
    assert MUSIC_TRACKS.config in DECLARED_CONFIGS


def test_the_teleport_list_lands_beside_the_partition() -> None:
    assert TELEPORT_ANCHORS.staged == "places/anchors.json"
    assert TELEPORT_ANCHORS.upstream == "locations.txt"


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
