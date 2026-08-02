"""Ask under a name that answers to nothing, and watch the model work out what was
meant without the api picking for it."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

from wiki_api.surfaces.mcp import CLOSE_NAMES_TOOL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_common import (
    CLAUDE_CODE,
    MISSED,
    OAUTH_BETA,
    TEST_DATA,
    TOKEN_VARIABLE,
    UNSURE,
    WORKED,
    Wiki,
    dataset,
    read_env,
    served,
    told,
    unready,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from pydantic_ai.messages import ModelMessage

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5"

MISSPELT = "king black dragn"
ASKED = f"tell me about the {MISSPELT}"
EXPECTED = "King Black Dragon"
SORT_TOOL = CLOSE_NAMES_TOOL
ASK_TOOL = "ask_user"
GIVEN = ("npc", EXPECTED)

SWEEP = (
    (MISSPELT, "npc", 5, 0.9),
    (MISSPELT, "location", 5, 0.9),
    (MISSPELT, "item", 5, 0.9),
    ("dragon scimmitar", "item", 5, 0.9),
    ("dragon scimmitar", "item", 5, 0.5),
    ("dragon scimmitar", "item", 2, 0.0),
)

PROMPT = (
    "Answer using only the 2009scape wiki tools available to you. Never answer from "
    "memory: this is a private game server whose data only those tools know. The "
    "name you are given may be misspelt. When a lookup answers to nothing, do not "
    "guess and do not settle it by searching. Ask whoever is asking, with the "
    f"{ASK_TOOL} tool, which sort of thing they meant, then call {SORT_TOOL} for "
    f"that sort and put what came back to them with {ASK_TOOL} so they can say which "
    f"one they meant. If a single name comes back, call {SORT_TOOL} once more with a "
    "lower keep, so they see what else was near enough to be worth offering rather "
    "than one name to take or leave. Look up only the name they picked, and keep the "
    "final answer to a sentence or two."
)


def parser() -> argparse.ArgumentParser:
    """How this demonstration is asked to run."""
    declared = argparse.ArgumentParser(
        prog="demo claude_fuzzy_match",
        description="Watch a misspelt name get settled by asking, not by guessing.",
    )
    declared.add_argument("question", nargs="?", default=ASKED)
    declared.add_argument(
        "--answer",
        action="append",
        default=None,
        help="answer the model's questions with these, in order, instead of typing",
    )
    declared.add_argument(
        "--scripted",
        action="store_true",
        help=f"answer with the built in {GIVEN} instead of typing",
    )
    return declared


def reaching(wiki: Wiki) -> StreamableHttpTransport:
    """How a client reaches the running wiki, key and all."""
    return StreamableHttpTransport(wiki.url, headers=wiki.headers)


def subscribed() -> bool:
    """Whether this run signs in with a subscription token rather than an api key."""
    return bool(os.environ.get(TOKEN_VARIABLE))


def model() -> AnthropicModel:
    """The model, signed in with whichever credential this run was given."""
    token = os.environ.get(TOKEN_VARIABLE)
    client = (
        AsyncAnthropic(auth_token=token, default_headers={"anthropic-beta": OAUTH_BETA})
        if token
        else AsyncAnthropic()
    )
    return AnthropicModel(MODEL, provider=AnthropicProvider(anthropic_client=client))


def identity() -> str | tuple[()]:
    """The first block of the system prompt, when there has to be one."""
    return CLAUDE_CODE if subscribed() else ()


def names_in(content: Any) -> list[str]:
    """The names an answer offered, whatever shape the client handed it back in."""
    found = getattr(content, "found", None)
    if found is None and isinstance(content, dict):
        found = content.get("found")
    if not found:
        return []
    names = []
    for candidate in found:
        name = getattr(candidate, "name", None)
        if name is None and isinstance(candidate, dict):
            name = candidate.get("name")
        if name:
            names.append(str(name))
    return names


async def how_close(wiki: Wiki) -> None:
    """Show what the two knobs on a near-name answer do, before any model runs."""
    print("  how close is close, asked directly:")
    print(f"    {'name':18} {'sort':9} {'k':>2} {'keep':>5}  offered")
    async with Client(reaching(wiki)) as client:
        for name, sort, limit, keep in SWEEP:
            answer = await client.call_tool(
                SORT_TOOL,
                {"name": name, "type": sort, "limit": limit, "keep": keep},
            )
            offered = names_in(answer.data) or ["(nothing close enough)"]
            print(f"    {name:18} {sort:9} {limit:>2} {keep:>5}  {', '.join(offered)}")


def answering(given: Iterator[str]) -> Callable[[str, list[str]], str]:
    """Name the tool the model reaches for when a name is not enough."""

    def ask_user(question: str, options: list[str]) -> str:
        """Put a question to the person who asked and give back their own words."""
        print(f"\n  the model asks: {question}")
        for option in options:
            print(f"    - {option}")
        answer = next(given, None)
        if answer is None:
            try:
                answer = input("  your answer: ").strip()
            except EOFError:
                answer = ""
        else:
            print(f"  your answer: {answer}   (given rather than typed)")
        return answer or "I do not know, offer me what you have"

    return ask_user


def steps(messages: Sequence[ModelMessage]) -> list[tuple[str, Any]]:
    """Every tool the model called, in the order it called them."""
    called: list[tuple[str, Any]] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                called.append((part.tool_name, part.args))
    return called


def offered(messages: Sequence[ModelMessage]) -> list[str]:
    """Every near name the server offered over the whole run, each said once."""
    names: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and part.tool_name == SORT_TOOL:
                names.extend(
                    name for name in names_in(part.content) if name not in names
                )
    return names


def first(called: Sequence[tuple[str, Any]], name: str) -> int | None:
    """Where a tool was first called, if it was."""
    return next((at for at, (tool, _) in enumerate(called) if tool == name), None)


def report(called: Sequence[tuple[str, Any]], near: Sequence[str], said: str) -> bool:
    """Say whether the run showed what this demonstration is here to show."""
    asked_at = first(called, ASK_TOOL)
    close_at = first(called, SORT_TOOL)
    asks = sum(1 for tool, _ in called if tool == ASK_TOOL)
    lines = []

    if asked_at is None:
        lines.append((MISSED, "the model never asked what sort of thing was meant"))
    elif close_at is None or asked_at < close_at:
        lines.append(
            (WORKED, "it asked which sort of thing before looking anything up")
        )
    else:
        lines.append((UNSURE, "it settled the sort itself before asking"))

    if close_at is None:
        lines.append((MISSED, f"it never called {SORT_TOOL}"))
    else:
        wanted = [args for tool, args in called if tool == SORT_TOOL]
        lines.append(
            (WORKED, f"it asked for close names {len(wanted)} time(s): {wanted}")
        )
        lines.append((WORKED, f"the server offered {', '.join(near) or '(nothing)'}"))

    if asks >= 2:
        lines.append((WORKED, "it came back to ask which of the close names was meant"))
    elif asks == 1:
        lines.append((UNSURE, "it only asked once, so nobody chose between the names"))
    else:
        lines.append((MISSED, "nobody was ever asked anything"))

    if EXPECTED.lower() in said.lower():
        lines.append((WORKED, f"the answer is about {EXPECTED}"))
    else:
        lines.append((UNSURE, f"the answer never mentions {EXPECTED}"))

    print("\n  what happened:")
    for outcome, note in lines:
        print(told(outcome, note))
    return all(outcome == WORKED for outcome, _ in lines)


async def run(wiki: Wiki, question: str, given: Iterator[str]) -> bool:
    """Put the question, printing every step it takes to settle the name."""
    agent = Agent(
        model(),
        output_type=str,
        toolsets=[MCPToolset(reaching(wiki))],
        system_prompt=identity(),
        instructions=PROMPT,
    )
    agent.tool_plain(answering(given))
    print(f"\n  asked: {question}")
    async with agent:
        answered = await agent.run(question)
    messages = answered.all_messages()
    for tool, args in steps(messages):
        print(f"    called {tool}({args})")
    print(f"\n  said: {answered.output.strip()}")
    return report(steps(messages), offered(messages), answered.output)


async def _main(question: str, given: Iterator[str]) -> int:
    with served() as wiki:
        print(f"  the wiki is answering at {wiki.url}, reading {dataset()}")
        print(f"  presenting the key issued to {wiki.kept}, id {wiki.key_id}")
        await how_close(wiki)
        return 0 if await run(wiki, question, given) else 1


def main() -> None:
    """Run the demonstration, typed at or scripted."""
    read_env(HERE)
    os.environ.setdefault("WIKI_API_DATA_DIR", TEST_DATA)
    asked = parser().parse_args()
    blocked = unready(HERE, signed_in_counts=False)
    if blocked is not None:
        print(blocked)
        raise SystemExit(1)
    answers = asked.answer or (list(GIVEN) if asked.scripted else [])
    raise SystemExit(asyncio.run(_main(asked.question, iter(answers))))


if __name__ == "__main__":
    main()
