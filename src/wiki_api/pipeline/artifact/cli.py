"""Turn the staged sources and the overlays into an artifact a surface can open."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from wiki_api.config import get_settings
from wiki_api.pipeline.artifact.build import build_artifact
from wiki_api.pipeline.build import build_from_sources


def parser() -> argparse.ArgumentParser:
    """Declare this command's arguments.

    Every path defaults to what the settings say, so an ordinary build names nothing;
    `--documents` builds from a directory of documents instead of the staged sources.
    """
    declared = argparse.ArgumentParser(
        prog="build-artifact",
        description="Build a knowledge artifact from the staged sources and overlays.",
    )
    declared.add_argument("--staged", type=Path, default=None)
    declared.add_argument("--overlays", type=Path, default=None)
    declared.add_argument("--identity", type=Path, default=None)
    declared.add_argument("--documents", type=Path, default=None)
    declared.add_argument("--destination", type=Path, default=None)
    declared.add_argument("--data-version", default=None)
    declared.add_argument("--game-version", default=None)
    return declared


def stamp(moment: datetime) -> str:
    """The data-version a build gets when nobody names one."""
    return moment.strftime("%Y.%m.%d.%H%M%S")


def main() -> None:
    """Build the artifact and say what went into it."""
    asked = parser().parse_args()
    settings = get_settings()
    destination = Path(asked.destination or settings.artifact_path)
    built_at = datetime.now(tz=UTC)
    data_version = asked.data_version or stamp(built_at)
    if asked.documents is not None:
        manifest = build_artifact(
            Path(asked.documents),
            destination,
            data_version=data_version,
            game_version=asked.game_version or UNKNOWN_GAME_VERSION,
            built_at=built_at,
        )
        print(
            f"built {manifest.data_version} at {destination} ({manifest.content_hash})"
        )
        return
    manifest, report = build_from_sources(
        Path(asked.staged or settings.staged_dir),
        Path(asked.overlays or settings.overlay_dir),
        Path(asked.identity or settings.identity_dir),
        destination,
        data_version=data_version,
        built_at=built_at,
    )
    for line in report.lines():
        print(line)
    print(f"  written to {destination} ({manifest.content_hash})")


UNKNOWN_GAME_VERSION = "2009scape@unknown"


if __name__ == "__main__":
    main()


# test cases


def test_an_ordinary_build_names_nothing_and_reads_the_settings() -> None:
    asked = parser().parse_args([])
    assert asked.staged is None
    assert asked.overlays is None
    assert asked.documents is None


def test_a_build_from_hand_made_documents_says_so() -> None:
    asked = parser().parse_args(["--documents", "tests/fixtures/knowledge"])
    assert asked.documents == Path("tests/fixtures/knowledge")


def test_where_a_build_lands_can_be_named() -> None:
    asked = parser().parse_args(["--destination", "out.sqlite3"])
    assert asked.destination == Path("out.sqlite3")


def test_a_build_nobody_named_still_gets_a_data_version() -> None:
    assert stamp(datetime(2026, 7, 30, 12, 30, 15, tzinfo=UTC)) == "2026.07.30.123015"


def test_two_builds_a_second_apart_are_told_apart() -> None:
    first = stamp(datetime(2026, 7, 30, 12, 30, 15, tzinfo=UTC))
    second = stamp(datetime(2026, 7, 30, 12, 30, 16, tzinfo=UTC))
    assert first != second


def test_a_build_from_staged_sources_reads_the_game_version_off_them() -> None:
    assert parser().parse_args([]).game_version is None
