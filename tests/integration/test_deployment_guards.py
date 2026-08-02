"""Check what a deployment is handed against what `Settings` will accept.

The Dockerfile, compose.yaml and deploy.example.json are read by docker rather than
imported, so a renamed field would leave all three naming something nothing answers to.
Asked with no daemon and no network, so they run on every change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from wiki_api.config import Settings

ROOT = Path(__file__).parent.parent.parent
EXAMPLE = ROOT / "deploy.example.json"
COMPOSE = ROOT / "compose.yaml"
IMAGE = ROOT / "Dockerfile"
PREFIX = "WIKI_API_"
NAMED = re.compile(rf"{PREFIX}[A-Z0-9_]+")
# Settings names no directory, so these two are read by wiki_api.access.paths rather
# than by the model, and are as real as any field.
OUTSIDE = {"WIKI_API_CONFIG_DIR", "WIKI_API_CONFIG_FILE"}


def _fields() -> set[str]:
    return set(Settings.model_fields)


def _settings_named_in(path: Path) -> set[str]:
    return set(NAMED.findall(path.read_text(encoding="utf-8")))


def test_the_example_deployment_is_written_in_lines_the_service_reads() -> None:
    """Every key is a field, and no field the example means to set is misspelt."""
    written = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    unknown = sorted(set(written) - _fields())
    assert not unknown, f"{EXAMPLE.name} sets {unknown}, which Settings does not have"


def test_the_example_deployment_would_start() -> None:
    """Its values validate, not just its keys.

    Read as a document rather than through the settings sources, so this says what the
    file itself holds and never what the machine running the suite happens to export.
    """
    written = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    settings = Settings.model_validate(written)
    assert settings.surfaces == "both"
    assert settings.guarded is True
    assert settings.data_dir == Path("/data")


def test_the_example_deployment_keeps_no_secret() -> None:
    """It is committed, so the only key it may name is one it does not contain."""
    written = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert not written["auth_public_key"]
    assert written["auth_public_key_file"]


def test_the_example_deployment_reads_what_the_image_mounts() -> None:
    """The paths it names are the ones the image declares as volumes."""
    written = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    declared = IMAGE.read_text(encoding="utf-8")
    assert 'VOLUME ["/data", "/config"]' in declared
    assert written["data_dir"] == "/data"
    for named in ("auth_public_key_file", "auth_revoked_file"):
        assert written[named].startswith("/config/")


@pytest.mark.parametrize("path", [COMPOSE, IMAGE], ids=lambda path: path.name)
def test_a_deployment_sets_nothing_the_service_does_not_read(path: Path) -> None:
    named = _settings_named_in(path)
    assert named, f"{path.name} names no settings at all, which cannot be right"
    unknown = sorted(
        found
        for found in named - OUTSIDE
        if found.removeprefix(PREFIX).lower() not in _fields()
    )
    assert not unknown, f"{path.name} sets {unknown}, which Settings does not read"


def test_the_image_and_the_example_agree_on_where_things_live() -> None:
    """Both name the same two directories, so neither can be moved on its own."""
    declared = IMAGE.read_text(encoding="utf-8")
    assert "WIKI_API_DATA_DIR=/data" in declared
    assert "WIKI_API_CONFIG_DIR=/config" in declared


def test_compose_reads_the_directories_the_preparation_fills() -> None:
    """`poe container prepare` writes these two, and compose mounts those two.

    Written down here because the two live in different files and nothing else would
    notice them drifting apart until a first start served an empty directory.
    """
    written = COMPOSE.read_text(encoding="utf-8")
    assert "./run/data:/data:ro" in written
    assert "./run/config:/config" in written
    prepared = (ROOT / "scripts" / "container.sh").read_text(encoding="utf-8")
    assert 'DATA_DIR="$RUN_DIR/data"' in prepared
    assert 'CONFIG_DIR="$RUN_DIR/config"' in prepared
