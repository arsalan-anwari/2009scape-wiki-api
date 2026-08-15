"""Ask Claude a few questions and report which of this server's tools it reached for."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from claude_agent_sdk.types import McpServerConfig, McpStdioServerConfig

from wiki_api.surfaces.mcp import SERVER_NAME, WRITTEN_TOOLS, followable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_common import (
    MISSED,
    ROOT,
    UNSURE,
    WORKED,
    Wiki,
    dataset,
    local_data,
    read_env,
    served,
    told,
    unready,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

HERE = Path(__file__).resolve().parent
MODEL = "sonnet"
MOST_TURNS = 8

PROMPT = (
    "Answer using only the 2009scape wiki tools available to you. Do not answer from "
    "memory: this is a private game server whose data only those tools know. Keep "
    "the answer to a sentence or two."
)


@dataclass(frozen=True)
class Question:
    """Something to ask, and what an answer that used this server would contain."""

    asked: str
    expects: str


ASKED = (
    Question("which npcs drop a dragon scimitar?", "king black dragon"),
    Question("how likely is the king black dragon to drop kbd heads?", "128"),
    Question("what does the crossbow shop sell, and for how much?", "wooden stock"),
    Question("where would i find the king black dragon?", "lair"),
    Question("what does the death plateau quest give you?", "climbing boots"),
)


def attached(wiki: Wiki) -> dict[str, McpServerConfig]:
    """Write down how to start the wiki, the way a client's own settings would."""
    spawned: McpStdioServerConfig = {
        "type": "stdio",
        "command": wiki.command,
        "args": list(wiki.arguments),
        "env": dict(wiki.settings),
    }
    return {SERVER_NAME: spawned}


def tool_names() -> list[str]:
    """Every tool this server offers, under the name a client calls it by."""
    offered = [*WRITTEN_TOOLS, *(followed.name for followed in followable())]
    return [f"mcp__{SERVER_NAME}__{name}" for name in offered]


async def ask(question: Question, wiki: Wiki) -> bool:
    """Put one question to Claude and report whether this server answered it."""
    options = ClaudeAgentOptions(
        mcp_servers=attached(wiki),
        allowed_tools=tool_names(),
        system_prompt=PROMPT,
        model=MODEL,
        max_turns=MOST_TURNS,
        setting_sources=[],
        cwd=str(ROOT),
    )
    called: list[str] = []
    said = ""
    async for message in query(prompt=question.asked, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    called.append(block.name)
                    print(f"    called {block.name}({block.input})")
                elif isinstance(block, TextBlock):
                    said += block.text
        elif isinstance(message, ResultMessage):
            said = said or str(message.result or "")
    return _reported(question, called, said)


def _reported(question: Question, called: Sequence[str], said: str) -> bool:
    reached = [name for name in called if name.startswith(f"mcp__{SERVER_NAME}__")]
    answered = question.expects.lower() in said.lower()
    print(f"    said: {said.strip()[:200]}")
    if not reached:
        print(told(MISSED, "claude never called this server"))
        return False
    if not answered:
        print(told(UNSURE, f"the answer does not mention {question.expects!r}"))
        return False
    print(told(WORKED, f"reached {len(reached)} tool(s) and answered from them"))
    return True


def _ready() -> str | None:
    """Whatever stands between this script and a working run."""
    blocked = unready(HERE)
    if blocked is not None:
        return blocked
    if shutil.which("claude") is None:
        return "claude code is not installed: https://claude.com/product/claude-code"
    return None


async def _main(questions: Sequence[Question]) -> int:
    worked = 0
    with served() as wiki:
        print(
            f"  claude starts the wiki itself as `{wiki.spawned}`, reading {dataset()}"
        )
        for question in questions:
            print(f"\n  asked: {question.asked}")
            if await ask(question, wiki):
                worked += 1
    print(f"\n{worked}/{len(questions)} questions were answered from this server")
    return 0 if worked == len(questions) else 1


def main() -> None:
    """Ask whatever was given on the command line, or the built in questions."""
    read_env(HERE)
    local_data()
    blocked = _ready()
    if blocked is not None:
        print(blocked)
        raise SystemExit(1)
    asked = tuple(Question(text, "") for text in sys.argv[1:]) or ASKED
    raise SystemExit(anyio.run(_main, asked))


if __name__ == "__main__":
    main()
