"""Turn a directory of documents into an artifact a surface can be pointed at."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from wiki_api.config import get_settings
from wiki_api.pipeline.artifact.build import build_artifact

UNKNOWN_GAME_VERSION = "2009scape@unknown"


def parser() -> argparse.ArgumentParser:
    """Declare this command's arguments.

    The source directory is required, so a build never guesses; only the output path
    defaults, to what the settings say.
    """
    declared = argparse.ArgumentParser(
        prog="build-artifact", description="Build a knowledge artifact from documents."
    )
    declared.add_argument("source", type=Path)
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


if __name__ == "__main__":
    main()


# test cases


def test_a_build_that_names_no_documents_is_refused() -> None:
    import pytest as testing

    with testing.raises(SystemExit):
        parser().parse_args([])


def test_where_a_build_lands_is_what_the_settings_say_unless_told() -> None:
    assert parser().parse_args(["some/where"]).destination is None


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
    asked = parser().parse_args(["some/where"])
    assert asked.game_version == UNKNOWN_GAME_VERSION
