"""Build the artifact from the staged sources plus the overlays."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.identity import EntityType
from wiki_api.pipeline.artifact.merge import merge
from wiki_api.pipeline.artifact.overlay import load_documents
from wiki_api.pipeline.artifact.writer import write_artifact
from wiki_api.pipeline.identity import read_allocation
from wiki_api.pipeline.reporting import BuildReport, report_of
from wiki_api.pipeline.sources.registry import defined_by, read_sources
from wiki_api.pipeline.sources.staged import StagedSources

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from wiki_api.domain.manifest import Manifest
    from wiki_api.pipeline.artifact.overlay import OverlaySource

UNKNOWN_GAME_VERSION = "2009scape@unknown"


def build_from_sources(
    staged_dir: Path,
    overlay_dir: Path,
    identity_dir: Path,
    destination: Path,
    *,
    data_version: str,
    built_at: datetime,
    strict: bool = True,
) -> tuple[Manifest, BuildReport]:
    """Build the artifact from the staged sources plus the overlays, and report it."""
    staged = StagedSources.at(staged_dir)
    overlays = _overlays(overlay_dir)
    outcomes = read_sources(
        staged, overlays, read_allocation(identity_dir, EntityType.QUEST)
    )
    documents = [outcome.read for outcome in outcomes]
    snapshot = merge([*documents, *overlays], strict=strict)
    manifest = write_artifact(
        snapshot,
        destination,
        data_version=data_version,
        game_version=_game_version(staged),
        built_at=built_at,
    )
    return manifest, report_of(
        data_version=manifest.data_version,
        game_version=str(manifest.game_version),
        entities=len(snapshot.entities),
        edges=len(snapshot.edges),
        prices=len(snapshot.prices),
        overlays=len(overlays),
        overridden=len(defined_by(overlays)),
        drifted=staged.drifted(),
        sources=outcomes,
    )


def _overlays(overlay_dir: Path) -> tuple[OverlaySource, ...]:
    if not overlay_dir.is_dir():
        return ()
    return load_documents(overlay_dir)


def _game_version(staged: StagedSources) -> str:
    versions = sorted({str(entry.game_version) for entry in staged.manifest.files})
    return versions[0] if versions else UNKNOWN_GAME_VERSION


# test cases


def _staged(tmp_path: Path) -> Path:
    import json

    from tests.sources import staged_from

    root = tmp_path / "source"
    staged_from(
        root,
        {
            "configs/item_configs.json": json.dumps(
                [{"id": "995", "name": "Coins"}, {"id": "536", "name": "Dragon bones"}]
            ),
            "configs/npc_configs.json": json.dumps([{"id": "50", "name": "KBD"}]),
            "configs/shops.json": "[]",
            "configs/drop_tables.json": json.dumps(
                [
                    {
                        "ids": "50",
                        "default": [
                            {
                                "id": "536",
                                "weight": "100.0",
                                "minAmount": "1",
                                "maxAmount": "1",
                            }
                        ],
                        "charm": [],
                        "main": [],
                    }
                ]
            ),
            "configs/npc_spawns.json": "[]",
            "configs/ground_spawns.json": "[]",
            "configs/ranged_weapon_configs.json": "[]",
            "tables/Quests.json": json.dumps(
                {
                    "enum": "Quests",
                    "source_file": "Quests.kt",
                    "language": "kotlin",
                    "columns": ["questName"],
                    "constants": [
                        {
                            "name": "DEATH_PLATEAU",
                            "values": {"questName": "Death Plateau"},
                        }
                    ],
                }
            ),
        },
    )
    return root


def _identity(tmp_path: Path) -> Path:
    from wiki_api.pipeline.identity import IdentityAllocation, write_allocation

    directory = tmp_path / "identity"
    write_allocation(
        directory,
        IdentityAllocation(type=EntityType.QUEST, ids={"DEATH_PLATEAU": 1}),
    )
    return directory


def _built(
    tmp_path: Path, overlays: Path | None = None
) -> tuple[Manifest, BuildReport]:
    from datetime import UTC, datetime

    return build_from_sources(
        _staged(tmp_path),
        overlays or (tmp_path / "overlays"),
        _identity(tmp_path),
        tmp_path / "knowledge.sqlite3",
        data_version="test-0001",
        built_at=datetime(2026, 8, 3, tzinfo=UTC),
    )


def test_a_build_from_staged_sources_carries_every_kind_of_fact(tmp_path: Path) -> None:
    manifest, report = _built(tmp_path)
    assert manifest.data_version == "test-0001"
    assert report.entities == 4
    assert report.edges == 1
    assert (tmp_path / "knowledge.sqlite3").is_file()


def test_the_artifact_says_which_commit_of_the_game_it_reflects(
    tmp_path: Path,
) -> None:
    manifest, _ = _built(tmp_path)
    assert manifest.game_version.repo == "2009scape"
    assert manifest.game_version.commit == "1f4a2c9"


def test_two_builds_of_one_staged_tree_are_identical(tmp_path: Path) -> None:
    first, _ = _built(tmp_path)
    second, _ = _built(tmp_path)
    assert first.content_hash == second.content_hash


def test_an_overlay_wins_over_the_source_it_corrects(tmp_path: Path) -> None:
    import json

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
                        "mode": "patch",
                        "description": "Lovely money!",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _, report = _built(tmp_path, overlays)
    assert report.overlays == 1


def test_a_build_reports_what_it_could_not_carry(tmp_path: Path) -> None:
    _, report = _built(tmp_path)
    told = "\n".join(report.lines())
    assert "item_configs.json" in told
    assert "Quests.kt" in told


def test_a_staged_file_edited_by_hand_is_reported_rather_than_hidden(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    staged = _staged(tmp_path)
    (staged / "configs/npc_configs.json").write_text(
        '[{"id": "50", "name": "KBD"}, {"id": "51", "name": "Guard"}]',
        encoding="utf-8",
    )
    _, report = build_from_sources(
        staged,
        tmp_path / "overlays",
        _identity(tmp_path),
        tmp_path / "knowledge.sqlite3",
        data_version="test-0002",
        built_at=datetime(2026, 8, 3, tzinfo=UTC),
    )
    assert report.drifted == ("configs/npc_configs.json",)


def test_a_build_with_no_overlays_at_all_still_runs(tmp_path: Path) -> None:
    _, report = _built(tmp_path, tmp_path / "nothing-here")
    assert report.overlays == 0
    assert report.overridden == 0
