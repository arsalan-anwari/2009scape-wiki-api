"""Fetch the published dataset, so every way of installing this can get one."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import PurePath
from typing import TYPE_CHECKING, Final

from wiki_api.config import Settings, settings_for_a_command

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

LEFT_BEHIND: Final = (".cache/huggingface", ".gitattributes", ".gitignore")
OWN_NAME: Final = "scape2009-wiki-data"
DISPATCHER: Final = "scape2009-wiki-api"


def invoked_as(argv0: str | None = None) -> str:
    """Name this command the way the reader just ran it."""
    called = PurePath(argv0 if argv0 is not None else sys.argv[0]).name
    return f"{DISPATCHER} data" if called.startswith(DISPATCHER) else OWN_NAME


class DatasetUnavailable(Exception):
    """The published dataset could not be fetched."""


def fetch(settings: Settings, *, only: Sequence[str] = ()) -> Path:
    """Put the published dataset where this deployment reads one, and say where."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as missing:  # pragma: no cover, the dependency is declared
        raise DatasetUnavailable(
            "fetching a dataset needs huggingface-hub, which this install is missing"
        ) from missing

    into = settings.data_dir
    into.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(
            repo_id=settings.hf_repo_id,
            repo_type="dataset",
            revision=settings.hf_revision,
            local_dir=str(into),
            allow_patterns=list(only) if only else None,
        )
    except Exception as failed:
        raise DatasetUnavailable(
            f"could not fetch {settings.hf_repo_id} ({settings.hf_revision}): {failed}"
        ) from failed
    _tidied(into)
    return into


def _tidied(into: Path) -> None:
    """Remove the bookkeeping the download leaves behind."""
    for name in LEFT_BEHIND:
        left = into / name
        if left.is_dir():
            shutil.rmtree(left, ignore_errors=True)
        elif left.is_file():
            left.unlink()
    cache = into / ".cache"
    if cache.is_dir() and not any(cache.iterdir()):
        cache.rmdir()


def main(argv: Sequence[str] | None = None) -> int:
    """Fetch a dataset, or say where this deployment looks for one."""
    parsed = _parser().parse_args(argv)
    settings = settings_for_a_command()
    if parsed.command == "where":
        return _said(settings)
    return _fetched(settings, parsed)


def _said(settings: Settings) -> int:
    artifact = settings.artifact_path
    print(f"directory: {settings.data_dir}")
    print(f"artifact:  {artifact}")
    print(f"published: {settings.hf_repo_id} ({settings.hf_revision})")
    if artifact.is_file():
        size = artifact.stat().st_size / 1_000_000
        print(f"there is a {size:.0f} MB build here")
        return 0
    print(f"there is no build here yet: fetch one with `{invoked_as()} pull`")
    return 1


def _fetched(settings: Settings, parsed: argparse.Namespace) -> int:
    if settings.artifact_path.is_file() and not parsed.force:
        print(f"a build is already at {settings.artifact_path}")
        print("fetch it again with --force")
        return 0
    only = (settings.artifact_filename,) if parsed.artifact_only else ()
    try:
        into = fetch(settings, only=only)
    except DatasetUnavailable as failed:
        print(f"error: {failed}", file=sys.stderr)
        return 1
    print(f"{settings.hf_repo_id} ({settings.hf_revision}) is in {into}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=invoked_as(),
        description=(
            "Fetch the published dataset into the directory this deployment serves "
            "from. Which dataset, which build of it and where it lands are the "
            "WIKI_API_HF_REPO_ID, WIKI_API_HF_REVISION and WIKI_API_DATA_DIR "
            "settings, or the matching lines of deploy.json."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pulling = commands.add_parser("pull", help="fetch the dataset")
    pulling.add_argument(
        "--force", action="store_true", help="fetch again over a build already here"
    )
    pulling.add_argument(
        "--artifact-only",
        action="store_true",
        help="only the file a surface opens, not the staged sources beside it",
    )
    commands.add_parser("where", help="say where a dataset is looked for")
    return parser


# test cases


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, auth_mode="off")


def test_a_dataset_is_fetched_into_the_directory_that_is_served(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    import wiki_api.dataset as fetching

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    asked: dict[str, object] = {}

    def remember(**given: object) -> str:
        asked.update(given)
        local = given["local_dir"]
        assert isinstance(local, str)
        return local

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type("Module", (), {"snapshot_download": staticmethod(remember)}),
    )
    settings = _settings(tmp_path)
    assert fetching.fetch(settings) == tmp_path
    assert asked["repo_id"] == settings.hf_repo_id
    assert asked["repo_type"] == "dataset"
    assert asked["local_dir"] == str(tmp_path)


def test_only_the_file_a_surface_opens_can_be_asked_for(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    import wiki_api.dataset as fetching

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    asked: dict[str, object] = {}

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type(
            "Module",
            (),
            {"snapshot_download": staticmethod(lambda **given: asked.update(given))},
        ),
    )
    fetching.fetch(_settings(tmp_path), only=("knowledge.sqlite3",))
    assert asked["allow_patterns"] == ["knowledge.sqlite3"]


def test_what_the_download_leaves_behind_is_cleared_away(tmp_path: Path) -> None:
    (tmp_path / ".cache" / "huggingface").mkdir(parents=True)
    (tmp_path / ".gitattributes").write_text("x", encoding="utf-8")
    _tidied(tmp_path)
    assert not (tmp_path / ".cache").exists()
    assert not (tmp_path / ".gitattributes").exists()


def test_a_failed_fetch_says_which_dataset_it_could_not_reach(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    import wiki_api.dataset as fetching

    assert isinstance(monkeypatch, pytest.MonkeyPatch)

    def refuse(**_: object) -> None:
        raise OSError("no route to host")

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        type("Module", (), {"snapshot_download": staticmethod(refuse)}),
    )
    with pytest.raises(DatasetUnavailable) as raised:
        fetching.fetch(_settings(tmp_path))
    assert "no route to host" in str(raised.value)


def test_where_a_dataset_is_looked_for_can_be_asked_without_fetching(
    tmp_path: Path, monkeypatch: object, capsys: object
) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "off")
    assert main(["where"]) == 1
    said = capsys.readouterr().out
    assert str(tmp_path) in said
    assert "scape2009-wiki-data pull" in said


def test_a_dataset_can_be_fetched_before_there_is_a_key_to_answer_with(
    tmp_path: Path, monkeypatch: object, capsys: object
) -> None:
    """A dataset is what there is to answer from, so needing a key to fetch one would
    leave a fresh install with nothing it could do in either order.
    """
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    monkeypatch.setenv("WIKI_API_CONFIG_DIR", str(tmp_path / "no-keys-made-yet"))
    monkeypatch.delenv("WIKI_API_AUTH_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(tmp_path))
    assert main(["where"]) == 1
    assert str(tmp_path) in capsys.readouterr().out


def test_a_build_already_here_is_not_fetched_over(
    tmp_path: Path, monkeypatch: object, capsys: object
) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    (tmp_path / "knowledge.sqlite3").write_text("a build", encoding="utf-8")
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "off")
    assert main(["pull"]) == 0
    assert "--force" in capsys.readouterr().out


def test_a_hint_names_the_command_the_reader_just_ran() -> None:
    """A container user has no `scape2009-wiki-data` on their PATH; they have `data`."""
    assert invoked_as("/usr/bin/scape2009-wiki-data") == OWN_NAME
    assert invoked_as("/app/.venv/bin/scape2009-wiki-api") == f"{DISPATCHER} data"
    assert invoked_as("scape2009-wiki-api") == f"{DISPATCHER} data"


def test_a_dataset_is_never_fetched_by_anything_that_serves() -> None:
    """The fetch is a command a person runs. A surface spawned by a client must not
    reach for the network on its way up.
    """
    from pathlib import Path as Location

    served = Location(__file__).parent / "surfaces"
    named = [
        path
        for path in served.rglob("*.py")
        if "wiki_api.dataset" in path.read_text(encoding="utf-8")
    ]
    assert named == []
