"""Turning a directory of documents into an artifact a surface can be pointed at."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from wiki_api.config import get_settings
from wiki_api.pipeline.artifact.build import build_artifact

FIXTURE_SOURCE = Path("tests/fixtures/knowledge")
UNKNOWN_GAME_VERSION = "2009scape@unknown"


def parser() -> argparse.ArgumentParser:
    """How this command is asked to build something."""
    declared = argparse.ArgumentParser(
        prog="build-artifact", description="Build a knowledge artifact from documents."
    )
    declared.add_argument("source", nargs="?", type=Path, default=FIXTURE_SOURCE)
    declared.add_argument("--destination", type=Path, default=None)
    declared.add_argument("--data-version", default=None)
    declared.add_argument("--game-version", default=UNKNOWN_GAME_VERSION)
    return declared


def stamp(moment: datetime) -> str:
    """The data-version a build gets when nobody names one."""
    return moment.strftime("%Y.%m.%d.%H%M%S")


def main() -> None:
    """Build the artifact and say where it went."""
    asked = parser().parse_args()
    settings = get_settings()
    destination = Path(asked.destination or settings.artifact_path)
    built_at = datetime.now(tz=UTC)
    manifest = build_artifact(
        Path(asked.source),
        destination,
        data_version=asked.data_version or stamp(built_at),
        game_version=asked.game_version,
        built_at=built_at,
    )
    print(f"built {manifest.data_version} at {destination} ({manifest.content_hash})")


# test cases


def test_the_hand_made_documents_are_what_it_builds_by_default() -> None:
    asked = parser().parse_args([])
    assert asked.source == FIXTURE_SOURCE
    assert asked.destination is None


def test_any_directory_of_documents_can_be_built_instead() -> None:
    asked = parser().parse_args(["some/where", "--destination", "out.sqlite3"])
    assert asked.source == Path("some/where")
    assert asked.destination == Path("out.sqlite3")


def test_a_build_nobody_named_still_gets_a_data_version() -> None:
    assert stamp(datetime(2026, 7, 30, 12, 30, 15, tzinfo=UTC)) == "2026.07.30.123015"


def test_two_builds_a_second_apart_are_told_apart() -> None:
    first = stamp(datetime(2026, 7, 30, 12, 30, 15, tzinfo=UTC))
    second = stamp(datetime(2026, 7, 30, 12, 30, 16, tzinfo=UTC))
    assert first != second


def test_a_build_says_which_game_it_reflects_even_when_it_cannot_tell() -> None:
    assert parser().parse_args([]).game_version == UNKNOWN_GAME_VERSION
