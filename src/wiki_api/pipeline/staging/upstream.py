"""Read which commit of the game's own repositories a staging run is reading."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Final

from wiki_api.domain.provenance import GameVersion
from wiki_api.pipeline.staging.errors import UpstreamUnreadable

if TYPE_CHECKING:
    from pathlib import Path

GIT: Final = "git"
HEAD: Final = "HEAD"
DIRTY_MARK: Final = "dirty"
GIT_TIMEOUT: Final = 30.0


def game_version_of(checkout: Path, repo: str) -> GameVersion:
    """Read the commit a checkout sits on, marking it when it has uncommitted work."""
    commit = _git(checkout, "rev-parse", HEAD)
    if _git(checkout, "status", "--porcelain"):
        commit = f"{commit}-{DIRTY_MARK}"
    return GameVersion(repo=repo, commit=commit)


def _git(checkout: Path, *arguments: str) -> str:
    if not checkout.is_dir():
        raise UpstreamUnreadable(str(checkout), "there is nothing checked out here")
    try:
        finished = subprocess.run(
            [GIT, "-C", str(checkout), *arguments],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise UpstreamUnreadable(str(checkout), str(error)) from error
    if finished.returncode != 0:
        raise UpstreamUnreadable(str(checkout), finished.stderr.strip() or "git failed")
    return finished.stdout.strip()


# test cases


def _repository(path: Path) -> None:
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.email", "test@example.test"),
        ("config", "user.name", "test"),
    ):
        subprocess.run([GIT, "-C", str(path), *arguments], check=True)


def _commit(path: Path, name: str) -> None:
    (path / name).write_text("{}", encoding="utf-8")
    subprocess.run([GIT, "-C", str(path), "add", "-A"], check=True)
    subprocess.run([GIT, "-C", str(path), "commit", "--quiet", "-m", name], check=True)


def test_a_checkout_reports_the_commit_it_sits_on(tmp_path: Path) -> None:
    _repository(tmp_path)
    _commit(tmp_path, "one.json")
    version = game_version_of(tmp_path, "2009scape")
    assert version.repo == "2009scape"
    assert version.commit is not None
    assert len(version.commit) == 40


def test_uncommitted_work_is_visible_in_the_version(tmp_path: Path) -> None:
    _repository(tmp_path)
    _commit(tmp_path, "one.json")
    (tmp_path / "one.json").write_text("[]", encoding="utf-8")
    version = game_version_of(tmp_path, "2009scape")
    assert version.commit is not None
    assert version.commit.endswith(DIRTY_MARK)


def test_a_directory_that_is_not_a_checkout_is_refused(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(UpstreamUnreadable):
        game_version_of(tmp_path / "absent", "2009scape")
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(UpstreamUnreadable):
        game_version_of(plain, "2009scape")
