"""Ask Claude a few questions and report which of this server's tools it reached for."""

from __future__ import annotations

import os
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
from dotenv import load_dotenv

from wiki_api.config import get_settings
from wiki_api.surfaces.mcp import SERVER_NAME, WRITTEN_TOOLS, followable

if TYPE_CHECKING:
    from collections.abc import Sequence

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENV = HERE / ".env"
CONFIG = ROOT / ".mcp.json"
MODEL = "sonnet"
MOST_TURNS = 8

WANTED = f"""no .env beside this demonstration. Create {ENV} containing:

    CLAUDE_CODE_OAUTH_TOKEN=

Generate the token with `claude setup-token`, which signs in with your Claude
subscription rather than pay-per-token api credits. Leave the value empty to use
whatever `claude` on this machine is already signed in as. Any WIKI_API_ setting put
in the same file is picked up too."""

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


def tool_names() -> list[str]:
    """Every tool this server offers, under the name a client calls it by."""
    offered = [*WRITTEN_TOOLS, *(followed.name for followed in followable())]
    return [f"mcp__{SERVER_NAME}__{name}" for name in offered]


async def ask(question: Question) -> bool:
    """Put one question to Claude and report whether this server answered it."""
    options = ClaudeAgentOptions(
        mcp_servers=CONFIG,
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
        print("    MISSED  claude never called this server")
        return False
    if not answered:
        print(f"    UNSURE  the answer does not mention {question.expects!r}")
        return False
    print(f"    WORKED  reached {len(reached)} tool(s) and answered from them")
    return True


def _ready() -> str | None:
    """Whatever stands between this script and a working run."""
    if not ENV.exists():
        return WANTED
    if shutil.which("claude") is None:
        return "claude code is not installed: https://claude.com/product/claude-code"
    if not CONFIG.exists():
        return f"no mcp configuration at {CONFIG}"
    if not get_settings().artifact_path.exists():
        return "no dataset yet: run `uv run poe build-artifact` first"
    signed_in = Path.home() / ".claude" / ".credentials.json"
    credentials = (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
    )
    if not any(os.environ.get(name) for name in credentials) and not signed_in.exists():
        return f"no way to sign in. Put a token in {ENV}, or run `claude` once"
    return None


async def _main(questions: Sequence[Question]) -> int:
    worked = 0
    for question in questions:
        print(f"\n  asked: {question.asked}")
        if await ask(question):
            worked += 1
    print(f"\n{worked}/{len(questions)} questions were answered from this server")
    return 0 if worked == len(questions) else 1


def main() -> None:
    """Ask whatever was given on the command line, or the built in questions."""
    load_dotenv(ENV)
    blocked = _ready()
    if blocked is not None:
        print(blocked)
        raise SystemExit(1)
    asked = tuple(Question(text, "") for text in sys.argv[1:]) or ASKED
    raise SystemExit(anyio.run(_main, asked))


if __name__ == "__main__":
    main()
