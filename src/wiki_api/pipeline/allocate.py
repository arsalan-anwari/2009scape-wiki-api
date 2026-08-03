"""Give a number to anything the sources name but do not number."""

from __future__ import annotations

import argparse
from pathlib import Path

from wiki_api.config import get_settings
from wiki_api.domain.identity import EntityType
from wiki_api.pipeline.identity import (
    IdentityAllocation,
    read_allocation,
    write_allocation,
)
from wiki_api.pipeline.sources.quests import source_keys
from wiki_api.pipeline.sources.staged import StagedSources


def parser() -> argparse.ArgumentParser:
    """Declare this command's arguments.

    Reading is the default, so a run that would hand out numbers has to say `--write`
    and the change lands in a file a reviewer reads.
    """
    declared = argparse.ArgumentParser(
        prog="allocate-ids",
        description="Number the quests the sources declare but never number.",
    )
    declared.add_argument("--staged", type=Path, default=None)
    declared.add_argument("--identity", type=Path, default=None)
    declared.add_argument("--write", action="store_true")
    return declared


def allocate(staged: StagedSources, current: IdentityAllocation) -> IdentityAllocation:
    """Extend the allocation with every natural key the staged table declares."""
    return current.extended_with(source_keys(staged))


def main() -> None:
    """Say which quests have no number yet, and hand them one when asked."""
    asked = parser().parse_args()
    settings = get_settings()
    identity = Path(asked.identity or settings.identity_dir)
    staged = StagedSources.at(Path(asked.staged or settings.staged_dir))
    current = read_allocation(identity, EntityType.QUEST)
    extended = allocate(staged, current)
    added = len(extended.ids) - len(current.ids)
    if not asked.write:
        print(f"{added} quests have no id yet, {len(current.ids)} already do")
        return
    path = write_allocation(identity, extended)
    print(f"numbered {added} quests, {len(extended.ids)} in all, written to {path}")


if __name__ == "__main__":
    main()


# test cases


def test_reading_is_the_default_and_writing_is_asked_for() -> None:
    assert parser().parse_args([]).write is False
    assert parser().parse_args(["--write"]).write is True


def test_where_the_numbers_are_kept_can_be_named() -> None:
    asked = parser().parse_args(["--identity", "elsewhere"])
    assert asked.identity == Path("elsewhere")


def test_every_declared_quest_ends_up_with_a_number(tmp_path: Path) -> None:
    import json

    from tests.sources import staged_from

    staged = staged_from(
        tmp_path,
        {
            "tables/Quests.json": json.dumps(
                {
                    "enum": "Quests",
                    "source_file": "Quests.kt",
                    "language": "kotlin",
                    "columns": ["questName"],
                    "constants": [
                        {"name": "COOKS_ASSISTANT", "values": {}},
                        {"name": "DEATH_PLATEAU", "values": {}},
                    ],
                }
            )
        },
    )
    allocation = allocate(staged, IdentityAllocation(type=EntityType.QUEST))
    assert allocation.ids == {"COOKS_ASSISTANT": 1, "DEATH_PLATEAU": 2}


def test_a_quest_already_numbered_keeps_its_number(tmp_path: Path) -> None:
    import json

    from tests.sources import staged_from

    staged = staged_from(
        tmp_path,
        {
            "tables/Quests.json": json.dumps(
                {
                    "enum": "Quests",
                    "source_file": "Quests.kt",
                    "language": "kotlin",
                    "columns": [],
                    "constants": [
                        {"name": "NEW_QUEST", "values": {}},
                        {"name": "DEATH_PLATEAU", "values": {}},
                    ],
                }
            )
        },
    )
    current = IdentityAllocation(type=EntityType.QUEST, ids={"DEATH_PLATEAU": 1})
    allocation = allocate(staged, current)
    assert allocation.ids["DEATH_PLATEAU"] == 1
    assert allocation.ids["NEW_QUEST"] == 2
