"""Check what a deployment is handed against what `Settings` will accept."""

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
    """Its values validate, not just its keys."""
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
    """The paths it names are the ones the image writes and reads."""
    written = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    declared = IMAGE.read_text(encoding="utf-8")
    assert 'VOLUME ["/config"]' in declared
    assert written["data_dir"] == "/data"
    for named in ("auth_public_key_file", "auth_revoked_file"):
        assert written[named].startswith("/config/")


def test_the_dataset_directory_is_never_declared_a_volume() -> None:
    """A build with the dataset in it fills /data, and a declared volume would copy all
    of it again on every start."""
    declared = IMAGE.read_text(encoding="utf-8")
    assert "/data" not in declared.split("VOLUME")[1].splitlines()[0]
    assert "COPY --from=dataset" in declared


def test_the_image_can_be_built_with_the_dataset_or_without_it() -> None:
    """Both stages the DATASET argument selects exist, or one of the two ways of
    building it names a stage that is not there.
    """
    declared = IMAGE.read_text(encoding="utf-8")
    assert "ARG DATASET=none" in declared
    for stage in ("dataset-none", "dataset-embedded"):
        assert f"AS {stage}" in declared
    assert "FROM dataset-${DATASET} AS dataset" in declared


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
    """`poe container prepare` writes these two, and compose mounts those two."""
    written = COMPOSE.read_text(encoding="utf-8")
    assert "./run/data:/data:ro" in written
    assert "./run/config:/config" in written
    prepared = (ROOT / "scripts" / "container.sh").read_text(encoding="utf-8")
    assert 'DATA_DIR="$RUN_DIR/data"' in prepared
    assert 'CONFIG_DIR="$RUN_DIR/config"' in prepared
