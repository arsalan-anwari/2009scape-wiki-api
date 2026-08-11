from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from wiki_api.surfaces.mcp import (
    CLOSE_NAMES_TOOL,
    SERVER_NAME,
    SORTS_TOOL,
    WRITTEN_TOOLS,
    followable,
)
from wiki_api.surfaces.mcp.naming import COMPARE_TOOL, MOVEMENT_TOOL
from wiki_api.surfaces.mcp.server import (
    ABOUT_DESCRIPTION,
    CLOSE_NAMES_DESCRIPTION,
    COMPARE_DESCRIPTION,
    GET_DESCRIPTION,
    LIST_DESCRIPTION,
    MOVEMENT_DESCRIPTION,
    SEARCH_DESCRIPTION,
    SORTS_DESCRIPTION,
)

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).parent.parent.parent
DEMOS = ROOT / "demos"
RUNNER = DEMOS / "run_demo.py"
COMMON = DEMOS / "claude_common.py"
SHARED = (RUNNER, COMMON)
ENTRY = "main.py"
QUOTED = re.compile(r"[\"'`](\w+)[\"'`]")
PREFIXED = re.compile(r"mcp__([\w-]+)__([\w*]+)")


def _folders() -> list[Path]:
    return sorted(path for path in DEMOS.iterdir() if (path / "README.md").is_file())


def _entries() -> list[Path]:
    return [folder / ENTRY for folder in _folders()]


def _modules() -> list[Path]:
    """Every file a demonstration is made of, including what they share."""
    return sorted(
        [*(path for folder in _folders() for path in folder.glob("*.py")), COMMON]
    )


def _loaded(path: Path) -> ModuleType:
    named = f"demo_{path.parent.name}_{path.stem}"
    spec = importlib.util.spec_from_file_location(named, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[named] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(named, None)
    return module


def _offered() -> set[str]:
    return set(WRITTEN_TOOLS) | {followed.name for followed in followable()}


def test_there_are_demonstrations_to_guard() -> None:
    assert _folders()
    assert _modules()


@pytest.mark.parametrize("folder", _folders(), ids=lambda path: path.name)
def test_every_demonstration_stands_on_its_own(folder: Path) -> None:
    assert (folder / "README.md").is_file()
    assert (folder / ENTRY).is_file(), f"{folder.name} has no {ENTRY} to start at"


def test_no_demonstration_leaves_loose_files_beside_the_others() -> None:
    """Only the runner and what every demonstration shares sit above the folders."""
    loose = [path.name for path in DEMOS.glob("*.py") if path not in SHARED]
    assert not loose, f"{loose} belong in a folder of their own"


def test_what_the_demonstrations_share_is_somewhere_they_can_all_reach() -> None:
    assert COMMON.is_file()
    assert COMMON.parent == DEMOS


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.parent.name)
def test_every_demonstration_still_imports(path: Path) -> None:
    _loaded(path)


@pytest.mark.parametrize("path", _entries(), ids=lambda path: path.parent.name)
def test_every_demonstration_starts_the_same_way(path: Path) -> None:
    assert callable(_loaded(path).main)


@pytest.mark.parametrize("folder", _folders(), ids=lambda path: path.name)
def test_every_demonstration_explains_what_it_costs(folder: Path) -> None:
    """Check the entry says what it does and the README says what a run costs.

    Cost is asked of the README, which a reader sees before running, not of the
    docstring.
    """
    assert (folder / ENTRY).read_text(encoding="utf-8").startswith('"""')
    assert "cost" in (folder / "README.md").read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("path", _modules(), ids=lambda path: path.parent.name)
def test_no_demonstration_writes_down_a_tool_name(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    written = {word for word in QUOTED.findall(source) if word in _offered()}
    assert not written, f"{path.name} writes down {sorted(written)}"


def test_every_tool_a_reader_is_pointed_at_exists() -> None:
    pointed = [
        found
        for folder in _folders()
        for found in PREFIXED.findall(
            (folder / "README.md").read_text(encoding="utf-8")
        )
    ]
    assert pointed
    for server, tool in pointed:
        assert server == SERVER_NAME
        assert tool == "*" or tool in _offered()


def test_the_committed_configuration_names_the_server_that_exists() -> None:
    configured = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    assert set(configured["mcpServers"]) == {SERVER_NAME}


def test_the_committed_configuration_runs_a_command_that_exists() -> None:
    configured = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    spawned = configured["mcpServers"][SERVER_NAME]["args"][-1]
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert spawned in declared["project"]["scripts"]


def test_what_the_demonstrations_need_is_declared() -> None:
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = declared["project"]["optional-dependencies"]
    assert extras["demos"]
    for path in _modules():
        _loaded(path)


def test_a_secret_a_demonstration_reads_is_never_committed() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in {line.strip() for line in ignored}
    assert not list(DEMOS.rglob(".env.example"))


@pytest.mark.parametrize("folder", _folders(), ids=lambda path: path.name)
def test_every_demonstration_says_it_proves_nothing(folder: Path) -> None:
    said = (folder / "README.md").read_text(encoding="utf-8").lower()
    assert "verif" in said
    assert "credential" in said


@pytest.mark.parametrize("folder", _folders(), ids=lambda path: path.name)
def test_every_demonstration_says_how_it_is_started(folder: Path) -> None:
    said = (folder / "README.md").read_text(encoding="utf-8")
    assert f"poe demo {folder.name}" in said


def test_a_demonstration_could_not_be_mistaken_for_the_gate() -> None:
    for path in _modules():
        source = path.read_text(encoding="utf-8")
        assert "def test_" not in source


def test_one_command_runs_any_demonstration() -> None:
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert RUNNER.name in declared["tool"]["poe"]["tasks"]["demo"]


def test_the_runner_offers_every_demonstration_there_is() -> None:
    assert _loaded(RUNNER).named() == [folder.name for folder in _folders()]


@pytest.mark.parametrize("folder", _folders(), ids=lambda path: path.name)
def test_the_runner_lets_a_demonstration_that_exists_start(folder: Path) -> None:
    assert _loaded(RUNNER).blocked(folder.name) is None


def test_the_runner_says_what_there_is_when_asked_for_nothing() -> None:
    said = _loaded(RUNNER).blocked("")
    assert said is not None
    for folder in _folders():
        assert folder.name in said


def test_the_runner_refuses_a_name_that_is_not_there() -> None:
    said = _loaded(RUNNER).blocked("nonesuch")
    assert said is not None
    assert "nonesuch" in said


def test_the_written_tools_a_reader_meets_are_the_ones_offered() -> None:
    described = {
        "search": SEARCH_DESCRIPTION,
        "get_thing": GET_DESCRIPTION,
        "list_things": LIST_DESCRIPTION,
        "about": ABOUT_DESCRIPTION,
        SORTS_TOOL: SORTS_DESCRIPTION,
        CLOSE_NAMES_TOOL: CLOSE_NAMES_DESCRIPTION,
        COMPARE_TOOL: COMPARE_DESCRIPTION,
        MOVEMENT_TOOL: MOVEMENT_DESCRIPTION,
    }
    assert set(described) == set(WRITTEN_TOOLS)
    assert set(described) <= _offered()
