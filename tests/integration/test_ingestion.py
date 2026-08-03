from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.sources import staged_from
from wiki_api.core.results import Direction, Found
from wiki_api.core.service import KnowledgeService
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.pipeline.build import build_from_sources
from wiki_api.pipeline.identity import IdentityAllocation, write_allocation
from wiki_api.pipeline.sources.registry import read_sources
from wiki_api.pipeline.sources.staged import StagedSources
from wiki_api.repository.factory import open_repository

if TYPE_CHECKING:
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.reporting import BuildReport

SLICES = (
    "item_configs.json",
    "npc_configs.json",
    "shops.json",
    "drop_tables.json",
    "npc_spawns.json",
    "ground_spawns.json",
    "ranged_weapon_configs.json",
)
BUILT_AT = datetime(2026, 8, 3, 12, tzinfo=UTC)
QUESTS = (
    "MYTHS_OF_THE_WHITE_LANDS",
    "BLACK_KNIGHTS_FORTRESS",
    "COOKS_ASSISTANT",
    "DEMON_SLAYER",
    "DORICS_QUEST",
)


def _slice(name: str) -> str:
    from tests.artifact import FIXTURE_KNOWLEDGE

    return (FIXTURE_KNOWLEDGE.parent / "sources" / name).read_text(encoding="utf-8")


def _staged(root: Path) -> StagedSources:
    files = {f"configs/{name}": _slice(name) for name in SLICES}
    files["tables/Quests.json"] = _slice("Quests.json")
    files["grand-exchange/2024-06-08.json"] = _slice("2024-06-08.json")
    return staged_from(root, files, prices=("grand-exchange/2024-06-08.json",))


def _identity(root: Path) -> Path:
    directory = root / "identity"
    write_allocation(
        directory,
        IdentityAllocation(
            type=EntityType.QUEST,
            ids={key: number for number, key in enumerate(QUESTS, start=1)},
        ),
    )
    return directory


def _built(root: Path, overlays: Path | None = None) -> tuple[Manifest, BuildReport]:
    _staged(root / "source")
    return build_from_sources(
        root / "source",
        overlays or (root / "overlays"),
        _identity(root),
        root / "knowledge.sqlite3",
        data_version="ingestion-0001",
        built_at=BUILT_AT,
    )


def _rows(
    service: KnowledgeService,
    name: str,
    rel: RelationshipType,
    direction: Direction = Direction.FORWARD,
    types: list[EntityType] | None = None,
) -> int:
    walked = service.walk_by_name(name, rel, direction, types=types)
    assert isinstance(walked.resolution, Found)
    return walked.resolution.value.rows.total


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    _built(tmp_path)
    return tmp_path / "knowledge.sqlite3"


def test_a_slice_of_the_real_sources_builds_an_artifact(tmp_path: Path) -> None:
    manifest, report = _built(tmp_path)
    assert manifest.data_version == "ingestion-0001"
    assert manifest.game_version.repo == "2009scape"
    assert report.entities > 0
    assert report.edges > 0
    assert report.prices > 0


def test_the_same_staged_sources_build_an_identical_artifact(tmp_path: Path) -> None:
    first, _ = _built(tmp_path / "first")
    second, _ = _built(tmp_path / "second")
    assert first.content_hash == second.content_hash
    assert (tmp_path / "first" / "knowledge.sqlite3").read_bytes() == (
        tmp_path / "second" / "knowledge.sqlite3"
    ).read_bytes()


def test_the_order_documents_are_read_in_does_not_change_the_artifact(
    tmp_path: Path,
) -> None:
    staged = _staged(tmp_path / "source")
    allocation = IdentityAllocation(
        type=EntityType.QUEST,
        ids={key: number for number, key in enumerate(QUESTS, start=1)},
    )
    outcomes = read_sources(staged, [], allocation)
    forwards = [outcome.read for outcome in outcomes]
    from wiki_api.pipeline.artifact.hashing import content_hash
    from wiki_api.pipeline.artifact.merge import merge

    backwards = list(reversed(forwards))
    assert content_hash(merge(forwards)) == content_hash(merge(backwards))


def test_every_question_the_model_promises_is_answered(artifact: Path) -> None:
    repository = open_repository(artifact)
    service = KnowledgeService(repository)
    try:
        named = service.lookup("Dragon bones", types=[EntityType.ITEM])
        assert isinstance(named.resolution, Found)
        assert named.resolution.value.name == "Dragon bones"
        assert _rows(service, "King Black Dragon", RelationshipType.DROPS) > 0
        assert (
            _rows(
                service,
                "Dragon bones",
                RelationshipType.DROPS,
                Direction.REVERSE,
                types=[EntityType.ITEM],
            )
            > 0
        )
        assert _rows(service, "Edgeville General Store", RelationshipType.SELLS) > 0
        assert repository.list_entities(EntityType.QUEST, limit=1).total == len(QUESTS)
        assert repository.price_history(995)
    finally:
        repository.close()


def test_a_page_descriptor_is_built_from_real_data(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        page = service.get_page(EntityKey(type=EntityType.ITEM, id=4587))
        assert isinstance(page, Found)
        assert page.value.infobox
        assert page.value.entity.label == "Dragon scimitar"
    finally:
        repository.close()


def test_a_noted_item_still_stands_beside_the_one_it_copies(artifact: Path) -> None:
    """Until the cache says which item is a note of which, both carry one name."""
    repository = open_repository(artifact)
    try:
        named = KnowledgeService(repository).lookup(
            "Dragon scimitar", types=[EntityType.ITEM]
        )
        assert named.alternatives
        assert [link.label for link in named.alternatives].count("Dragon scimitar") >= 1
    finally:
        repository.close()


def test_a_near_name_still_answers_against_real_names(artifact: Path) -> None:
    repository = open_repository(artifact)
    try:
        service = KnowledgeService(repository)
        near = service.near_names("dragon scimitr", EntityType.ITEM, limit=3)
        assert [row.link.label for row in near.items][:1] == ["Dragon scimitar"]
    finally:
        repository.close()


def test_an_overlay_beats_the_source_it_corrects(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "corrections.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "item",
                        "id": 995,
                        "name": "Coins",
                        "description": "Corrected by hand.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _built(tmp_path, overlays)
    repository = open_repository(tmp_path / "knowledge.sqlite3")
    try:
        entity = repository.get_entity(EntityKey(type=EntityType.ITEM, id=995))
        assert entity is not None
        assert entity.description == "Corrected by hand."
    finally:
        repository.close()


def test_a_spawn_lands_in_a_place_an_overlay_names(tmp_path: Path) -> None:
    overlays = tmp_path / "overlays"
    overlays.mkdir()
    (overlays / "places.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "source": "overlay",
                "game_version": "2009scape@1f4a2c9",
                "precedence": 10,
                "entities": [
                    {
                        "type": "location",
                        "id": 1,
                        "name": "Lumbridge",
                        "source_key": "misthalin/lumbridge",
                        "attributes": {
                            "kind": "town",
                            "bounds": {
                                "min_x": 3200,
                                "min_y": 3200,
                                "max_x": 3260,
                                "max_y": 3260,
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _, report = _built(tmp_path, overlays)
    placed = [source for source in report.sources if source.source == "npc_spawns.json"]
    assert placed[0].edges > 0


def test_with_no_places_named_no_spawn_becomes_a_placement(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    spawns = [source for source in report.sources if source.source == "npc_spawns.json"]
    assert spawns[0].edges == 0
    assert spawns[0].skipped_by_reason().get("no_place")


def test_a_build_tells_a_reader_what_it_could_not_carry(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    told = "\n".join(report.lines())
    assert "item_configs.json" in told
    assert "source rows did not become facts" in told
