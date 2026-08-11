"""Write the overlays a person finishes by hand, filled in as far as evidence goes."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from wiki_api.config import get_settings
from wiki_api.domain.identity import EntityType
from wiki_api.pipeline.allocate import NUMBERED
from wiki_api.pipeline.artifact.overlay import load_documents
from wiki_api.pipeline.identity import read_allocation
from wiki_api.pipeline.prefill.quests import (
    DETAIL_FILE,
    REQUIREMENTS_FILE,
    detail_overlay,
    requirements_overlay,
    written,
)
from wiki_api.pipeline.sources.journal import folded
from wiki_api.pipeline.sources.registry import read_sources
from wiki_api.pipeline.sources.staged import StagedSources

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wiki_api.domain.identity import EntityKey


def parser() -> argparse.ArgumentParser:
    """Declare this command's arguments.

    An overlay that already exists is left alone, because by then somebody has edited
    it; `--force` is how a caller says to throw that away.
    """
    declared = argparse.ArgumentParser(
        prog="prefill-overlays",
        description="Write the overlays a person finishes, prefilled with what the "
        "sources support.",
    )
    declared.add_argument("--staged", type=Path, default=None)
    declared.add_argument("--identity", type=Path, default=None)
    declared.add_argument("--overlays", type=Path, default=None)
    declared.add_argument("--force", action="store_true")
    return declared


def subjects(
    staged: StagedSources, identity: Path, overlays: Path
) -> tuple[Mapping[str, EntityKey], frozenset[EntityKey], Mapping[int, str]]:
    """Every declared quest by the folded name a guide calls it, and every key a
    requirement is allowed to point at, which is why the whole read is done here.
    """
    loaded = load_documents(overlays) if overlays.is_dir() else ()
    outcomes = read_sources(
        staged,
        loaded,
        {
            entity_type: read_allocation(identity, entity_type)
            for entity_type in NUMBERED
        },
    )
    entities = [
        entity for outcome in outcomes for entity in outcome.read.document.entities
    ]
    entities.extend(
        entity for overlay in loaded for entity in overlay.document.entities
    )
    quests = {
        folded(entity.name): entity.key
        for entity in entities
        if entity.type is EntityType.QUEST and entity.name
    }
    names = {
        entity.key.id: entity.name
        for entity in entities
        if entity.type is EntityType.QUEST and entity.name
    }
    return quests, frozenset(entity.key for entity in entities), names


def main() -> None:
    """Write every overlay a person finishes, saying what each was filled in from."""
    asked = parser().parse_args()
    settings = get_settings()
    staged = StagedSources.at(Path(asked.staged or settings.staged_dir))
    identity = Path(asked.identity or settings.identity_dir)
    overlays = Path(asked.overlays or settings.overlay_dir)
    quests, known, names = subjects(staged, identity, overlays)
    print(
        written(
            overlays / REQUIREMENTS_FILE,
            requirements_overlay(staged, quests, known, names),
            force=asked.force,
        )
    )
    print(
        written(
            overlays / DETAIL_FILE,
            detail_overlay(staged, quests, names),
            force=asked.force,
        )
    )


if __name__ == "__main__":
    main()


# test cases


def test_leaving_an_edited_overlay_alone_is_the_default() -> None:
    assert parser().parse_args([]).force is False
    assert parser().parse_args(["--force"]).force is True


def test_every_path_the_command_uses_can_be_pointed_somewhere_else() -> None:
    asked = parser().parse_args(["--staged", "a", "--identity", "b", "--overlays", "c"])
    assert (asked.staged, asked.identity, asked.overlays) == (
        Path("a"),
        Path("b"),
        Path("c"),
    )
