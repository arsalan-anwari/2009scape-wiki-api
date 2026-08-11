"""Decode the game cache into staged tables, counting what it could not read."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict

from wiki_api.pipeline.cache.datamaps import DATAMAP_INDEX, decode_datamap
from wiki_api.pipeline.cache.errors import CacheError
from wiki_api.pipeline.cache.items import decode_item
from wiki_api.pipeline.cache.landscape import decode_landscape, region_name
from wiki_api.pipeline.cache.maplabels import decode_map_label
from wiki_api.pipeline.cache.npcs import decode_npc
from wiki_api.pipeline.cache.reader import (
    ITEM_INDEX,
    MAP_INDEX,
    NPC_INDEX,
    SCENERY_INDEX,
    WORLDMAP_INDEX,
    CacheReader,
)
from wiki_api.pipeline.cache.scenery import decode_scenery
from wiki_api.pipeline.cache.xtea import read_region_keys

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

REGIONS: Final = 256 * 256
NO_KEY: Final = (0, 0, 0, 0)
KEYS_FILE: Final = "xteas.json"
REVISION: Final = "index {index} revision {revision}"
LABEL_ARCHIVE: Final = 2


class DecodeOutcome(BaseModel):
    """What one index decoded to, and what it refused."""

    model_config = ConfigDict(frozen=True)

    index: int
    revision: int
    records: tuple[dict[str, Any], ...] = ()
    read: int = 0
    kept: int = 0
    refused: tuple[str, ...] = ()

    @property
    def revision_note(self) -> str:
        return REVISION.format(index=self.index, revision=self.revision)

    @property
    def note(self) -> str:
        told = f"index {self.index}: {self.kept} of {self.read} decoded"
        if len(self.records) != self.kept:
            told = f"{told}, {len(self.records)} rows"
        return told if not self.refused else f"{told}, {len(self.refused)} refused"


def decode_definitions(
    reader: CacheReader, index: int, decode: Callable[[int, bytes], BaseModel]
) -> DecodeOutcome:
    """Decode every definition in one index, keeping the ones that read cleanly."""
    records: list[dict[str, Any]] = []
    refused: list[str] = []
    read = 0
    for identity, body in reader.definitions(index):
        read += 1
        try:
            records.append(decode(identity, body).model_dump(mode="json"))
        except CacheError as error:
            refused.append(str(error))
    return DecodeOutcome(
        index=index,
        revision=reader.table(index).revision,
        records=tuple(records),
        read=read,
        kept=len(records),
        refused=tuple(refused),
    )


def decode_placements(
    reader: CacheReader, keys: Mapping[int, tuple[int, ...]]
) -> DecodeOutcome:
    """Decode every map region that opens, region by region in a stable order."""
    table = reader.table(MAP_INDEX)
    records: list[dict[str, Any]] = []
    refused: list[str] = []
    read = 0
    opened = 0
    for region_id in range(REGIONS):
        archive = table.archive_named(region_name(region_id))
        if archive is None:
            continue
        read += 1
        try:
            files = reader.archive(MAP_INDEX, archive, keys.get(region_id, NO_KEY))
            placements = decode_landscape(region_id, files[0])
        except CacheError as error:
            refused.append(f"region {region_id}: {error}")
            continue
        opened += 1
        records.extend(
            {"region": region_id, **placed.model_dump(mode="json")}
            for placed in placements
        )
    return DecodeOutcome(
        index=MAP_INDEX,
        revision=table.revision,
        records=tuple(records),
        read=read,
        kept=opened,
        refused=tuple(refused),
    )


def decode_map_labels(reader: CacheReader) -> DecodeOutcome:
    """Decode the one archive of the world map index that names part of the world."""
    table = reader.table(WORLDMAP_INDEX)
    records: list[dict[str, Any]] = []
    refused: list[str] = []
    read = 0
    try:
        files = reader.archive(WORLDMAP_INDEX, LABEL_ARCHIVE, NO_KEY)
    except CacheError as error:
        return DecodeOutcome(
            index=WORLDMAP_INDEX, revision=table.revision, refused=(str(error),)
        )
    for identity, body in enumerate(files):
        read += 1
        try:
            records.append(decode_map_label(identity, body).model_dump(mode="json"))
        except CacheError as error:
            refused.append(str(error))
    return DecodeOutcome(
        index=WORLDMAP_INDEX,
        revision=table.revision,
        records=tuple(records),
        read=read,
        kept=len(records),
        refused=tuple(refused),
    )


def decode_cache(cache: Path, configs: Path) -> dict[str, DecodeOutcome]:
    """Decode every index this build reads, in the order the plan lands them."""
    reader = CacheReader.at(
        cache,
        indexes=(
            ITEM_INDEX,
            SCENERY_INDEX,
            NPC_INDEX,
            DATAMAP_INDEX,
            MAP_INDEX,
            WORLDMAP_INDEX,
        ),
    )
    keys = read_region_keys(configs / KEYS_FILE)
    return {
        "items": decode_definitions(reader, ITEM_INDEX, decode_item),
        "scenery": decode_definitions(reader, SCENERY_INDEX, decode_scenery),
        "npcs": decode_definitions(reader, NPC_INDEX, decode_npc),
        "datamaps": decode_definitions(reader, DATAMAP_INDEX, decode_datamap),
        "placements": decode_placements(reader, keys),
        "maplabels": decode_map_labels(reader),
    }


# test cases


def _reader(tmp_path: Path) -> CacheReader:
    from tests.cache import built_cache

    return CacheReader.at(
        built_cache(tmp_path / "cache"),
        indexes=(ITEM_INDEX, SCENERY_INDEX, NPC_INDEX, MAP_INDEX),
    )


def test_an_index_decodes_to_records_that_carry_their_revision(tmp_path: Path) -> None:
    outcome = decode_definitions(_reader(tmp_path), ITEM_INDEX, decode_item)
    assert outcome.read == 1
    assert outcome.records[0]["name"] == "Dragon scimitar"
    assert outcome.records[0]["value"] == 100000
    assert outcome.revision_note == "index 19 revision 214"
    assert outcome.refused == ()


def test_a_definition_that_does_not_decode_is_counted_not_dropped(
    tmp_path: Path,
) -> None:
    from wiki_api.pipeline.cache.errors import UnknownOpcode

    def refuse(identity: int, body: bytes) -> BaseModel:
        raise UnknownOpcode("item", identity, 138, 0)

    outcome = decode_definitions(_reader(tmp_path), ITEM_INDEX, refuse)
    assert outcome.records == ()
    assert outcome.read == 1
    assert len(outcome.refused) == 1
    assert "138" in outcome.refused[0]
    assert "1 refused" in outcome.note


def test_the_world_map_index_decodes_to_the_names_it_draws(tmp_path: Path) -> None:
    from tests.cache import built_cache

    reader = CacheReader.at(built_cache(tmp_path / "cache"), indexes=(WORLDMAP_INDEX,))
    outcome = decode_map_labels(reader)
    assert outcome.read == 1
    assert outcome.records[0]["name"] == "Lumbridge"
    assert outcome.records[0]["x"] == 3222
    assert outcome.refused == ()


def test_a_world_map_index_that_will_not_open_is_counted_not_raised(
    tmp_path: Path,
) -> None:
    from tests.cache import archive, container, reference_table, write_cache

    directory = write_cache(
        tmp_path / "cache",
        {WORLDMAP_INDEX: {2: container(archive([b"\x00"]))}},
        {WORLDMAP_INDEX: container(reference_table({3: [0]}))},
    )
    reader = CacheReader.at(directory, indexes=(WORLDMAP_INDEX,))
    outcome = decode_map_labels(reader)
    assert outcome.records == ()
    assert len(outcome.refused) == 1


def test_a_region_decodes_to_the_placements_it_holds(tmp_path: Path) -> None:
    outcome = decode_placements(_reader(tmp_path), {})
    assert outcome.read == 1
    assert outcome.kept == 1
    assert outcome.records[0]["region"] == (50 << 8) | 50
    assert outcome.records[0]["type"] == 1
    assert outcome.refused == ()


def test_a_region_that_needs_a_key_nobody_has_is_counted(tmp_path: Path) -> None:
    from tests.cache import archive, container, encrypted, reference_table, write_cache

    directory = write_cache(
        tmp_path / "locked",
        {MAP_INDEX: {0: encrypted(archive([bytes([0])]), (1, 2, 3, 4))}},
        {MAP_INDEX: container(reference_table({0: [0]}, names={0: "l50_50"}))},
    )
    reader = CacheReader.at(directory, indexes=(MAP_INDEX,))
    outcome = decode_placements(reader, {})
    assert outcome.read == 1
    assert outcome.records == ()
    assert len(outcome.refused) == 1
    assert "region 12850" in outcome.refused[0]


def test_a_region_opens_when_its_key_is_known(tmp_path: Path) -> None:
    from tests.cache import archive, container, encrypted, reference_table, write_cache

    region = bytes([1, 2, 0b000100, 0, 0])
    directory = write_cache(
        tmp_path / "locked",
        {MAP_INDEX: {0: encrypted(archive([region]), (1, 2, 3, 4))}},
        {MAP_INDEX: container(reference_table({0: [0]}, names={0: "l50_50"}))},
    )
    reader = CacheReader.at(directory, indexes=(MAP_INDEX,))
    outcome = decode_placements(reader, {12850: (1, 2, 3, 4)})
    assert len(outcome.records) == 1
    assert outcome.refused == ()
