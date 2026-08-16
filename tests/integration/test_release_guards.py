"""Check that everything naming a version names the same one, and that the packages
describe files that are really there.

CHANGELOG.md is where a version is decided and `scripts/release.sh sync` is what spreads
it. Nothing else would notice the three falling out of step until a release was half
published.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from wiki_api.config import Settings

ROOT = Path(__file__).parent.parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
PROJECT = ROOT / "pyproject.toml"
PACKAGING = ROOT / "packaging"
NFPM = PACKAGING / "nfpm.yaml"
SYSTEM_DEPLOY = PACKAGING / "deploy.system.json"
RELEASE = ROOT / "scripts" / "release.sh"

RELEASED = re.compile(r"^## +\[?(\d+\.\d+\.\d+)[^]]*\]?", re.MULTILINE)
NUMBERED = re.compile(r"^\d+\.\d+\.\d+$")


def _declared() -> str:
    """Read the version CHANGELOG.md declares, the way release.sh reads it."""
    found = RELEASED.search(CHANGELOG.read_text(encoding="utf-8"))
    assert found is not None, f"{CHANGELOG.name} declares no version"
    return found.group(1)


def _project_version() -> str:
    section = PROJECT.read_text(encoding="utf-8").split("[project]", 1)[1]
    found = re.search(r'^version *= *"([^"]+)"', section, re.MULTILINE)
    assert found is not None
    return found.group(1)


def _nfpm_version() -> str:
    described = NFPM.read_text(encoding="utf-8")
    found = re.search(r'^version: *"?([^"\n]+)"?', described, re.MULTILINE)
    assert found is not None
    return found.group(1)


def test_the_changelog_declares_a_version_release_can_read() -> None:
    assert NUMBERED.match(_declared())


def test_the_package_is_the_version_the_changelog_declares() -> None:
    """Run `bash scripts/release.sh sync` when this fails."""
    assert _project_version() == _declared()


def test_the_system_packages_are_that_version_too() -> None:
    """Run `bash scripts/release.sh sync` when this fails."""
    assert _nfpm_version() == _declared()


def test_the_changelog_says_what_changed_and_not_only_that_it_did() -> None:
    """The section becomes the release notes, and an empty one publishes a blank
    page.
    """
    text = CHANGELOG.read_text(encoding="utf-8")
    body = text.split(f"[{_declared()}]", 1)[1]
    assert len([line for line in body.splitlines() if line.startswith("- ")]) >= 1


def test_every_file_a_package_ships_is_really_there() -> None:
    """The paths nfpm.yaml names outside dist/, which is built and never committed."""
    described = NFPM.read_text(encoding="utf-8")
    for named in re.findall(r"^ *- src: \./(\S+)", described, re.MULTILINE):
        if named.startswith("dist/"):
            continue
        assert (ROOT / named).exists(), f"nfpm.yaml ships {named}, which is not there"


def test_the_installed_deployment_is_written_in_lines_the_service_reads() -> None:
    """Every key is a field, and no field it means to set is misspelt."""
    written = json.loads(SYSTEM_DEPLOY.read_text(encoding="utf-8"))
    unknown = sorted(set(written) - set(Settings.model_fields))
    assert not unknown, f"{SYSTEM_DEPLOY.name} sets {unknown}, which Settings lacks"


def test_the_installed_deployment_would_start() -> None:
    """Its values validate, and it answers only key holders as a package should."""
    written = json.loads(SYSTEM_DEPLOY.read_text(encoding="utf-8"))
    settings = Settings.model_validate(written)
    assert settings.guarded is True
    assert settings.data_dir == Path("/usr/share/scape2009-wiki-api")


def test_the_installed_deployment_reads_what_the_packages_put_where() -> None:
    """The dataset and the key it names are the paths nfpm.yaml installs them to."""
    written = json.loads(SYSTEM_DEPLOY.read_text(encoding="utf-8"))
    described = NFPM.read_text(encoding="utf-8")
    assert f"dst: {written['data_dir']}/" in described
    assert "dst: /etc/scape2009-wiki-api/deploy.json" in described
    for named in ("auth_public_key_file", "auth_revoked_file"):
        assert written[named].startswith("/etc/scape2009-wiki-api/")


@pytest.mark.parametrize(
    "command", ["scape2009-wiki-serve", "scape2009-wiki-mcp", "scape2009-wiki-keys"]
)
def test_a_package_installs_the_commands_a_wheel_installs(command: str) -> None:
    """The names are the same however it was installed, or a reader of the README has to
    learn two sets.
    """
    assert (PACKAGING / "linux" / command).is_file()
    assert command in PROJECT.read_text(encoding="utf-8")


def test_the_release_script_publishes_nothing_without_being_told_to() -> None:
    """`--yes` is what turns publish from a description into a push."""
    written = RELEASE.read_text(encoding="utf-8")
    assert 'if [[ "$CONFIRMED" -eq 0 ]]; then' in written
    assert "--yes) CONFIRMED=1" in written
