"""Stage the game's sources into the directory every build reads."""

from __future__ import annotations

import argparse
from pathlib import Path

from wiki_api.config import get_settings
from wiki_api.pipeline.staging.collectors import COLLECTORS, StagingRun, stage


def parser() -> argparse.ArgumentParser:
    """Declare this command's arguments.

    Every path defaults to what the settings say, so a staging run names nothing it
    does not mean to override.
    """
    declared = argparse.ArgumentParser(
        prog="stage-sources",
        description="Copy, extract and fetch the game's sources into data/source.",
    )
    declared.add_argument("--game-data", type=Path, default=None)
    declared.add_argument("--destination", type=Path, default=None)
    declared.add_argument(
        "--only", action="append", choices=sorted(COLLECTORS), default=None
    )
    return declared


def main() -> None:
    """Stage the sources and say what landed."""
    asked = parser().parse_args()
    settings = get_settings()
    run = StagingRun(
        game_data=Path(asked.game_data or settings.game_data_dir),
        destination=Path(asked.destination or settings.staged_dir),
        prices_url=settings.ge_data_url,
    )
    report = stage(run, only=asked.only or ())
    for line in report.lines():
        print(line)


if __name__ == "__main__":
    main()


# test cases


def test_staging_with_no_arguments_takes_every_path_from_the_settings() -> None:
    asked = parser().parse_args([])
    assert asked.game_data is None
    assert asked.destination is None
    assert asked.only is None


def test_one_source_can_be_staged_on_its_own() -> None:
    asked = parser().parse_args(["--only", "tables"])
    assert asked.only == ["tables"]


def test_several_sources_can_be_named_at_once() -> None:
    asked = parser().parse_args(["--only", "configs", "--only", "tables"])
    assert asked.only == ["configs", "tables"]


def test_a_collector_nobody_declares_is_refused_before_anything_runs() -> None:
    import pytest as testing

    with testing.raises(SystemExit):
        parser().parse_args(["--only", "images"])


def test_where_the_sources_come_from_and_land_can_both_be_named() -> None:
    asked = parser().parse_args(
        ["--game-data", "elsewhere", "--destination", "out/source"]
    )
    assert asked.game_data == Path("elsewhere")
    assert asked.destination == Path("out/source")
