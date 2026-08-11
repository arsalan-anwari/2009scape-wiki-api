"""Ask the wiki a question of every shape it can be asked and count how much of the
data model an answer could actually reach.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from claude_common import (
    CLAUDE_CODE,
    MISSED,
    OAUTH_BETA,
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
from claude_complex_query.probes import PROBES, Probe

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator, Sequence
    from typing import TextIO

    from pydantic_ai.messages import ModelMessage

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5"

FULL_DATA = "data"

CLARIFY = "ask_to_clarify"
CONFIRM = "ask_to_confirm"
CHOOSE = "ask_to_choose"
MORE = "ask_for_more"
ASK_TOOLS = (CLARIFY, CONFIRM, CHOOSE, MORE)

FALLBACK = "I do not mind, use your judgement and tell me what you chose"
YES = "yes, go on"
FIRST = "the first one"

PROMPT = (
    "Answer using only the 2009scape wiki tools available to you. Never answer from "
    "memory: this is a private game server, and its numbers differ from the public "
    "game even where the names match. If the tools do not hold something, say so "
    "plainly rather than filling it in.\n"
    "\n"
    "Four tools reach the person who asked, and they are the only way to get anything "
    f"from them. Use {CLARIFY} when the question is too vague to look anything up "
    f"for. Use {CONFIRM} when you have settled on a reading that could be wrong. Use "
    f"{CHOOSE} when several things answer to one name, or when a lookup came back "
    "unknown and you have close names to offer, and never choose between them "
    f"yourself. Use {MORE} before spending another page on a long answer, saying how "
    "much you have shown and how much there is.\n"
    "\n"
    "Answers arrive one page at a time and report a total; read further only with the "
    "offset the last answer gave you. Keep the final answer to a few sentences, and "
    "give the numbers the wiki gave you rather than rounding them away."
)


def parser() -> argparse.ArgumentParser:
    """How this demonstration is asked to run."""
    declared = argparse.ArgumentParser(
        prog="demo claude_complex_query",
        description="Ask questions of every shape and count what could be answered.",
    )
    declared.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="TAG",
        help="run just these probes, by tag; repeatable",
    )
    declared.add_argument(
        "--list", action="store_true", help="print the probes and what each covers"
    )
    declared.add_argument(
        "--scripted",
        action="store_true",
        help="answer the model's questions from each probe instead of typing",
    )
    declared.add_argument(
        "--log",
        type=Path,
        default=None,
        metavar="FILE",
        help="also write everything this run prints to this file, replacing it",
    )
    return declared


class _Tee(io.TextIOBase):
    """Write every line to the terminal and to the log at once."""

    def __init__(self, terminal: TextIO, log: TextIO) -> None:
        super().__init__()
        self._terminal = terminal
        self._log = log

    def write(self, s: str) -> int:
        written = self._terminal.write(s)
        self._terminal.flush()
        self._log.write(s)
        self._log.flush()
        return written

    def flush(self) -> None:
        self._terminal.flush()
        self._log.flush()

    def isatty(self) -> bool:
        return self._terminal.isatty()


@contextmanager
def logged(where: Path | None) -> Generator[None]:
    """Copy everything this run prints into `where`, as well as to the terminal."""
    if where is None:
        yield
        return
    where.parent.mkdir(parents=True, exist_ok=True)
    kept_out, kept_err = sys.stdout, sys.stderr
    with where.open("w", encoding="utf-8") as writing:
        sys.stdout = _Tee(kept_out, writing)
        sys.stderr = _Tee(kept_err, writing)
        try:
            yield
        finally:
            sys.stdout, sys.stderr = kept_out, kept_err


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


def asking(given: Iterator[str], scripted: bool) -> tuple[Callable[..., str], ...]:
    """The four ways the model may turn back to whoever asked."""

    def answered(shown: str, standing: str) -> str:
        print(f"\n  the model asks: {shown}")
        reply = next(given, None)
        if reply is not None:
            print(f"  your answer: {reply}   (given rather than typed)")
        elif scripted:
            print(f"  your answer: {standing}   (the standing answer, unasked)")
            reply = standing
        else:
            try:
                reply = input("  your answer: ").strip()
            except EOFError:
                reply = ""
        return reply or standing

    def ask_to_clarify(question: str) -> str:
        """Ask for the missing part of a question too vague to look anything up for."""
        return answered(question, FALLBACK)

    def ask_to_confirm(question: str, proposal: str) -> str:
        """Check a reading of the question with whoever asked before acting on it."""
        return answered(f"{question}\n    proposing: {proposal}", YES)

    def ask_to_choose(question: str, options: list[str]) -> str:
        """Put candidates to whoever asked and use the one they pick, never your own."""
        offered = "\n".join(f"    - {option}" for option in options)
        first = f"{FIRST}, {options[0]}" if options else FIRST
        return answered(f"{question}\n{offered}", first)

    def ask_for_more(question: str, shown: int, total: int) -> str:
        """Ask whether to read on, saying how much is shown and how much there is."""
        return answered(f"{question}\n    shown {shown} of {total}", YES)

    return (ask_to_clarify, ask_to_confirm, ask_to_choose, ask_for_more)


def steps(messages: Sequence[ModelMessage]) -> list[tuple[str, Any]]:
    """Every tool the model called, in the order it called them."""
    called: list[tuple[str, Any]] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                called.append((part.tool_name, part.args))
    return called


def report(probe: Probe, called: Sequence[tuple[str, Any]], said: str) -> bool:
    """Say whether this probe showed what it is here to show."""
    names = [tool for tool, _ in called]
    from_wiki = [tool for tool in names if tool not in ASK_TOOLS]
    asked = [tool for tool in names if tool in ASK_TOOLS]
    spoken = said.lower()
    lines: list[tuple[str, str]] = []

    ways = len(set(from_wiki))
    if not from_wiki and not asked:
        lines.append((MISSED, "the model called nothing at all"))
    elif not from_wiki:
        lines.append((UNSURE, "it only ever asked, and never read the wiki"))
    else:
        lines.append((WORKED, f"it read the wiki {len(from_wiki)} time(s)"))

    if probe.reaches and ways >= probe.reaches:
        lines.append((WORKED, f"it read the wiki {ways} different ways"))
    elif probe.reaches:
        lines.append(
            (UNSURE, f"it read the wiki {ways} ways, and this asks for {probe.reaches}")
        )

    if probe.human_turn:
        if asked:
            lines.append(
                (WORKED, f"it turned back to ask: {', '.join(sorted(set(asked)))}")
            )
        else:
            lines.append((MISSED, "it settled the question itself instead of asking"))
    elif asked:
        lines.append((UNSURE, f"it asked when it did not have to: {', '.join(asked)}"))

    for wanted in probe.says:
        if wanted.lower() in spoken:
            lines.append((WORKED, f"the answer carries {wanted!r}"))
        else:
            lines.append((UNSURE, f"the answer never mentions {wanted!r}"))

    if probe.says_any and not any(one.lower() in spoken for one in probe.says_any):
        lines.append((UNSURE, "the answer does not admit the gap it was asked about"))
    elif probe.says_any:
        lines.append((WORKED, "the answer says the wiki does not hold this"))

    print("\n  what happened:")
    for outcome, note in lines:
        print(told(outcome, note))
    return all(outcome == WORKED for outcome, _ in lines)


async def offered_by(wiki: Wiki) -> list[str]:
    """Every tool the running wiki puts in front of a client, under its own name."""
    async with Client(reaching(wiki)) as client:
        return sorted(tool.name for tool in await client.list_tools())


async def run(
    probe: Probe, wiki: Wiki, given: Iterator[str], scripted: bool
) -> tuple[bool, list[str]]:
    """Put one probe, printing every step, and say whether it showed what it should."""
    agent = Agent(
        model(),
        output_type=str,
        toolsets=[MCPToolset(reaching(wiki))],
        system_prompt=identity(),
        instructions=PROMPT,
    )
    for reaching_back in asking(given, scripted):
        agent.tool_plain(reaching_back)

    print(f"\n{'=' * 78}")
    print(f"  {probe.tag}: {probe.covers}")
    print(f"  asked: {probe.question}")
    async with agent:
        answered = await agent.run(probe.question)
    called = steps(answered.all_messages())
    for tool, args in called:
        print(f"    called {tool}({args})")
    print(f"\n  said: {answered.output.strip()}")
    worked = report(probe, called, answered.output)
    return worked, [tool for tool, _ in called]


def coverage(offered: Sequence[str], reached: Counter[str]) -> None:
    """Print which of the wiki's own tools this sweep ever exercised."""
    touched = [name for name in offered if reached.get(name)]
    untouched = [name for name in offered if not reached.get(name)]
    print(f"\n  tool coverage: {len(touched)} of {len(offered)} the wiki offers")
    if untouched:
        print("    never called by any probe:")
        for name in untouched:
            print(f"      {name}")


def summarise(outcomes: Sequence[tuple[str, bool]], asks: Counter[str]) -> int:
    """Print how the sweep went, and give back what this process should exit with."""
    worked = [tag for tag, ok in outcomes if ok]
    fell_short = [tag for tag, ok in outcomes if not ok]
    print(
        f"\n  probes: {len(worked)} of {len(outcomes)} showed everything asked of them"
    )
    if fell_short:
        print(f"    fell short: {', '.join(fell_short)}")
    if asks:
        turns = ", ".join(f"{name} x{count}" for name, count in sorted(asks.items()))
        print(f"  human turns: {turns}")
    else:
        print("  human turns: none, which for this sweep is a failure of its own")
    return 0 if not fell_short else 1


def chosen(only: Sequence[str] | None) -> tuple[Probe, ...]:
    """The probes this run puts, and nothing else."""
    if not only:
        return PROBES
    wanted = set(only)
    return tuple(probe for probe in PROBES if probe.tag in wanted)


async def _main(probes: Sequence[Probe], scripted: bool) -> int:
    with served(data_dir=os.environ["WIKI_API_DATA_DIR"]) as wiki:
        print(f"  the wiki is answering at {wiki.url}, reading {dataset()}")
        print(f"  presenting the key issued to {wiki.kept}, id {wiki.key_id}")
        offered = await offered_by(wiki)
        print(
            f"  it offers {len(offered)} tools, and this sweep puts "
            f"{len(probes)} questions"
        )

        reached: Counter[str] = Counter()
        asks: Counter[str] = Counter()
        outcomes: list[tuple[str, bool]] = []
        for probe in probes:
            given = iter(probe.answers if scripted else ())
            worked, called = await run(probe, wiki, given, scripted)
            outcomes.append((probe.tag, worked))
            reached.update(called)
            asks.update(name for name in called if name in ASK_TOOLS)

        print(f"\n{'=' * 78}")
        coverage(offered, reached)
        return summarise(outcomes, asks)


def listed() -> None:
    """Print every probe and what it is here to cover, without asking anything."""
    for probe in PROBES:
        print(f"  {probe.tag:18} {probe.covers}")


def main() -> None:
    """Run the sweep, typed at or scripted, into a log file if one was named."""
    read_env(HERE)
    asked = parser().parse_args()
    try:
        with logged(asked.log):
            code = _sweep(asked)
    finally:
        if asked.log is not None:
            print(f"  this run was written to {asked.log}")
    raise SystemExit(code)


def _sweep(asked: argparse.Namespace) -> int:
    os.environ.setdefault("WIKI_API_DATA_DIR", FULL_DATA)

    if asked.list:
        listed()
        return 0

    blocked = unready(HERE, signed_in_counts=False)
    if blocked is not None:
        print(blocked)
        return 1

    probes = chosen(asked.only)
    if not probes:
        print("no probe by that tag. There is:")
        listed()
        return 2
    return asyncio.run(_main(probes, asked.scripted))


if __name__ == "__main__":
    main()
