"""Decode the game cache into ordinary records, at staging and never at build time."""

from wiki_api.pipeline.cache.errors import (
    ArchiveUnreadable,
    CacheError,
    CacheMissing,
    IndexMissing,
    MalformedContainer,
    TruncatedDefinition,
    UnknownOpcode,
)
from wiki_api.pipeline.cache.items import ItemDefinitionRecord, decode_item
from wiki_api.pipeline.cache.landscape import Placement, decode_landscape, region_name
from wiki_api.pipeline.cache.npcs import NpcDefinitionRecord, decode_npc
from wiki_api.pipeline.cache.reader import (
    ITEM_INDEX,
    MAP_INDEX,
    NPC_INDEX,
    SCENERY_INDEX,
    CacheReader,
)
from wiki_api.pipeline.cache.scenery import SceneryDefinitionRecord, decode_scenery
from wiki_api.pipeline.cache.xtea import read_region_keys

__all__ = [
    "ITEM_INDEX",
    "MAP_INDEX",
    "NPC_INDEX",
    "SCENERY_INDEX",
    "ArchiveUnreadable",
    "CacheError",
    "CacheMissing",
    "CacheReader",
    "IndexMissing",
    "ItemDefinitionRecord",
    "MalformedContainer",
    "NpcDefinitionRecord",
    "Placement",
    "SceneryDefinitionRecord",
    "TruncatedDefinition",
    "UnknownOpcode",
    "decode_item",
    "decode_landscape",
    "decode_npc",
    "decode_scenery",
    "read_region_keys",
    "region_name",
]
