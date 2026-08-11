"""Read which commit of the game's own repositories a staging run is reading, and name
a vendored directory that has no commit to read.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Final

from wiki_api.domain.provenance import GameVersion
from wiki_api.pipeline.staging.errors import UpstreamUnreadable

GIT: Final = "git"
HEAD: Final = "HEAD"
DIRTY_MARK: Final = "dirty"
GIT_TIMEOUT: Final = 30.0
TOPLEVEL: Final = "--show-toplevel"
CONTENT_DIGEST: Final = 12
VCS_DIRECTORY: Final = ".git"


def game_version_of(checkout: Path, repo: str) -> GameVersion:
    """Read the commit a checkout sits on, marking it when it has uncommitted work.

    A directory that merely sits inside somebody else's checkout is refused, because
    git would otherwise answer for the repository above it.
    """
    _own_checkout(checkout)
    commit = _git(checkout, "rev-parse", HEAD)
    if _git(checkout, "status", "--porcelain"):
        commit = f"{commit}-{DIRTY_MARK}"
    return GameVersion(repo=repo, commit=commit)


def vendored_version_of(directory: Path, name: str) -> GameVersion:
    """Name a vendored directory by what it holds, since it carries no commit."""
    if not directory.is_dir():
        raise UpstreamUnreadable(str(directory), "there is nothing vendored here")
    running = hashlib.sha256()
    for path in sorted(_vendored_files(directory)):
        running.update(path.relative_to(directory).as_posix().encode("utf-8"))
        running.update(path.read_bytes())
    return GameVersion(repo=name, commit=running.hexdigest()[:CONTENT_DIGEST])


def _vendored_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*")
        if path.is_file() and VCS_DIRECTORY not in path.relative_to(directory).parts
    ]


def _own_checkout(checkout: Path) -> None:
    toplevel = _git(checkout, "rev-parse", TOPLEVEL)
    if Path(toplevel).resolve() != checkout.resolve():
        raise UpstreamUnreadable(
            str(checkout), f"this is part of the checkout at {toplevel}, not one itself"
        )


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


def test_a_directory_inside_someone_elses_checkout_is_refused(tmp_path: Path) -> None:
    import pytest

    _repository(tmp_path)
    _commit(tmp_path, "one.json")
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    (vendored / "locations.txt").write_text("Varrock 3210,3424\n", encoding="utf-8")
    with pytest.raises(UpstreamUnreadable) as caught:
        game_version_of(vendored, "2009scape-telecoordinates")
    assert "not one itself" in str(caught.value)


def test_a_vendored_directory_is_named_by_what_it_holds(tmp_path: Path) -> None:
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    (vendored / "locations.txt").write_text("Varrock 3210,3424\n", encoding="utf-8")
    version = vendored_version_of(vendored, "2009scape-telecoordinates")
    assert version.repo == "2009scape-telecoordinates"
    assert version.commit is not None
    assert len(version.commit) == CONTENT_DIGEST


def test_an_edit_to_a_vendored_file_changes_the_version(tmp_path: Path) -> None:
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    named = vendored / "locations.txt"
    named.write_text("Varrock 3210,3424\n", encoding="utf-8")
    before = vendored_version_of(vendored, "telecoordinates")
    named.write_text("Varrock 3210,3425\n", encoding="utf-8")
    assert vendored_version_of(vendored, "telecoordinates") != before


def test_a_vendored_directory_reads_the_same_twice(tmp_path: Path) -> None:
    vendored = tmp_path / "vendored"
    (vendored / "deep").mkdir(parents=True)
    (vendored / "one.txt").write_text("one", encoding="utf-8")
    (vendored / "deep" / "two.txt").write_text("two", encoding="utf-8")
    assert vendored_version_of(vendored, "pages") == vendored_version_of(
        vendored, "pages"
    )


def test_a_vendored_directory_that_is_absent_is_refused(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(UpstreamUnreadable):
        vendored_version_of(tmp_path / "absent", "pages")


def test_a_repository_underneath_a_vendored_directory_is_not_part_of_it(
    tmp_path: Path,
) -> None:
    vendored = tmp_path / "vendored"
    vendored.mkdir()
    (vendored / "one.txt").write_text("one", encoding="utf-8")
    before = vendored_version_of(vendored, "pages")
    _repository(vendored)
    _commit(vendored, "two.json")
    (vendored / "two.json").unlink()
    assert vendored_version_of(vendored, "pages") == before
