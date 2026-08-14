from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

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
    from collections.abc import Callable
    from types import ModuleType

    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.run import AgentRunResult

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


def _sweep() -> ModuleType:
    return _loaded(DEMOS / "claude_complex_query" / ENTRY)


def _replies(
    turns: list[ModelResponse],
) -> Callable[[list[ModelMessage], AgentInfo], ModelResponse]:
    spent: list[int] = []

    def replying(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        spent.append(len(messages))
        return turns[min(len(spent) - 1, len(turns) - 1)]

    return replying


def _notes(tag: str = "asked", covers: str = "one question") -> Any:
    """Somewhere for a stub run to keep what it did."""
    from claude_complex_query.probes import Probe
    from claude_complex_query.report import Notes

    return Notes(probe=Probe(tag=tag, covers=covers, question="what drops these?"))


def _asked(
    turns: list[ModelResponse], question: str = "where do these come from?"
) -> tuple[ModuleType, AgentRunResult[str], Any]:
    """Put one question to a stub model, never to a real one."""
    from claude_complex_query.report import Loud

    sweep = _sweep()
    notes = _notes()
    agent = Agent(FunctionModel(_replies(turns)), output_type=str)

    @agent.tool_plain
    def look_up(name: str) -> str:
        """Look one thing up."""
        return f"read {name}"

    answered = anyio.run(lambda: sweep.stepped(agent, question, notes, Loud()))
    return sweep, answered, notes


def _showed(sweep: ModuleType, probe: Any, called: list[str], said: str) -> bool:
    """Whether a probe met every expectation it declared."""
    from claude_common import WORKED

    lines = sweep.checked(probe, called, said, said)
    return all(outcome == WORKED for outcome, _ in lines)


def test_a_step_is_kept_when_it_is_taken_rather_than_when_the_probe_ends(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A probe that has stopped and a probe still thinking read identically when
    nothing is kept until the end, and one of them is worth interrupting.
    """
    turns = [
        ModelResponse(parts=[ToolCallPart("look_up", {"name": "Raw salmon"})]),
        ModelResponse(parts=[TextPart("They come from fishing spots.")]),
    ]
    _, answered, notes = _asked(turns)
    printed = capsys.readouterr().out
    assert "called look_up(name='Raw salmon')" in printed
    assert [event.written() for event in notes.events] == ["look_up(name='Raw salmon')"]
    assert answered.output == "They come from fishing spots."


def test_the_closing_answer_is_kept_once_rather_than_twice() -> None:
    """The last turn calls nothing and its words are the answer, which the document
    holds whole; keeping them among the steps as well would print it twice.
    """
    turns = [
        ModelResponse(parts=[ToolCallPart("look_up", {"name": "Raw salmon"})]),
        ModelResponse(parts=[TextPart("They come from fishing spots.")]),
    ]
    _, answered, notes = _asked(turns)
    assert answered.output not in [
        getattr(event, "words", "") for event in notes.events
    ]


def test_what_a_probe_says_while_reading_counts_as_something_it_said() -> None:
    """A long answer read a page at a time says half of itself before it asks whether
    to read on, and that half was still said to whoever asked.
    """
    turns = [
        ModelResponse(
            parts=[
                TextPart("Here are the first ten, starting with Dragon bones."),
                ToolCallPart("look_up", {"name": "Dragon bones"}),
            ]
        ),
        ModelResponse(parts=[TextPart("That is all of them.")]),
    ]
    sweep, answered, _ = _asked(turns)
    said = sweep.spoken(answered.all_messages())
    assert "Dragon bones" in said
    assert "Dragon bones" not in answered.output


def test_a_probe_that_asks_when_it_may_is_not_marked_down_for_it() -> None:
    """The instructions tell the model to ask before spending another page, so a
    probe scoring that as a fault marks it down for following them.
    """
    sweep = _sweep()
    from claude_complex_query.probes import MORE, Probe

    probe = Probe(tag="paged", covers="a long answer", question="what drops these?")
    assert MORE in probe.may_ask
    assert _showed(sweep, probe, ["drops", MORE, "drops"], "the answer")


def test_a_probe_fails_when_it_says_the_wiki_holds_what_it_holds() -> None:
    sweep = _sweep()
    from claude_complex_query.probes import DENIALS, Probe

    probe = Probe(
        tag="denied",
        covers="a fact the artifact carries",
        question="what warns me about these?",
        says=(),
        never_says=DENIALS,
    )
    denied = f"Slayer level 72, and the wiki {DENIALS[0]} a warning."
    assert not _showed(sweep, probe, ["get_thing"], denied)
    assert _showed(sweep, probe, ["get_thing"], "Slayer level 72.")


def _document(where: Path) -> tuple[Any, Any]:
    """A document with one probe in it, and the notes that probe left."""
    from datetime import datetime

    from claude_complex_query.report import Document

    notes = _notes(tag="paged", covers="a long answer")
    return Document(where=where, started=datetime.now(), total=1), notes


def test_an_answer_written_in_markdown_stays_inside_the_block_that_holds_it(
    tmp_path: Path,
) -> None:
    """A model that answers in fenced markdown would end the block early at three
    backticks, and the rest of its answer would be read as the page around it.
    """
    document, notes = _document(tmp_path / "run.md")
    notes.said = 'Here is the shape of it:\n\n```json\n{"schema": 9}\n```'
    document.add(notes)
    written = (tmp_path / "run.md").read_text(encoding="utf-8")
    assert "````markdown" in written
    assert '{"schema": 9}' in written


def test_a_probe_that_came_apart_still_leaves_what_it_reached(tmp_path: Path) -> None:
    """The document is written after every probe, so a sweep given up on halfway is
    still a document rather than nothing.
    """
    from claude_complex_query.report import Call

    document, notes = _document(tmp_path / "run.md")
    notes.events = [Call("look_up", {"name": "Raw salmon"})]
    notes.broke = "this probe was given up on after 10m 00s"
    document.add(notes)
    written = (tmp_path / "run.md").read_text(encoding="utf-8")
    assert "look_up(name='Raw salmon')" in written
    assert "given up on" in written
    assert "## paged" in written


def test_every_probe_can_be_reached_from_the_table_at_the_top(tmp_path: Path) -> None:
    document, notes = _document(tmp_path / "run.md")
    document.add(notes)
    document.close(["look_up"], {"look_up": 1}, {}, 12.0)
    written = (tmp_path / "run.md").read_text(encoding="utf-8")
    assert "(#paged)" in written
    assert "## paged" in written
    assert "## At a glance" in written
