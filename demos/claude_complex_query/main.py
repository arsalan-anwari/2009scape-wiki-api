"""Ask the wiki a question of every shape it can be asked and count how much of the
data model an answer could actually reach.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
import httpx
from anthropic import AsyncAnthropic
from fastmcp import Client
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import TextPart, ToolCallPart
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
    local_data,
    read_env,
    served,
    unready,
)
from claude_complex_query.probes import PROBES, Probe
from claude_complex_query.report import (
    Ask,
    Bar,
    Call,
    Document,
    Loud,
    Notes,
    Said,
    Screen,
    took,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from fastmcp.client.transports import StdioTransport
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.run import AgentRunResult

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5"

STALL = 2.0
THINKING = 120.0
PATIENCE = 600.0
REDRAW = 0.5

HELD_BACK: frozenset[int] = frozenset({408, 409, 429, 500, 502, 503, 504, 529})
MOST_WAITS = 6
FIRST_WAIT = 2.0
LONGEST_WAIT = 90.0

CLARIFY = "ask_to_clarify"
CONFIRM = "ask_to_confirm"
CHOOSE = "ask_to_choose"
MORE = "ask_for_more"
ASK_TOOLS = (CLARIFY, CONFIRM, CHOOSE, MORE)

ADDRESSING = re.compile(
    r"\b(?:item|npc|shop|quest|location|scenery|task|room|music):\d+"
    r"|\b(?:id|ids|npc|item|track|region|plane)\s*#?\s*\d+"
    r"|\b[xy]\s+\d{3,}",
    re.IGNORECASE,
)
MOST_ADDRESSING = 4

FALLBACK = "I do not mind, use your judgement and tell me what you chose"
YES = "yes, go on"
FIRST = "the first one"

FORMAT = (
    "Lay every answer out the same way:\n"
    "\n"
    "1. Open with one sentence that answers the question outright, in bold where a "
    "single name or number is the answer. No preamble, and never restate the "
    "question.\n"
    "2. Then the detail, in whichever of these the answer actually is:\n"
    "   - a markdown table when three or more things are being compared on the same "
    "fields, one row each, the number that was asked about in the first column after "
    "the name;\n"
    "   - a bullet list when it is a flat set of things, or one thing with several "
    "values, each bullet `**name** — the fact`;\n"
    "   - a plain sentence or two when it is a single fact, with no list at all.\n"
    "3. Close with one line saying what the wiki does not hold, but only when "
    "something asked for is missing from it. Nothing was left out, nothing to write.\n"
    "\n"
    "Keep it short: the opening sentence plus at most twelve rows or bullets. Give "
    "the numbers the wiki gave you rather than rounding them away, and write them "
    "the way a player says them (`1/5000`, `20,000 Magic XP`, `level 72`)."
)

PROMPT = (
    "Answer using only the 2009scape wiki tools available to you. Never answer from "
    "memory: this is a private game server, and its numbers differ from the public "
    "game even where the names match. If the tools do not hold something, say so "
    "plainly rather than filling it in.\n"
    "\n"
    "Four tools reach the person who asked, and they are the only way to get anything "
    f"from them. Use {CLARIFY} when the question is too vague to look anything up "
    f"for. Use {CONFIRM} when you have settled on a reading that could be wrong. Use "
    f"{CHOOSE} when several things answer to one name and the wiki records something "
    "that tells them apart, or when a lookup came back unknown and you have close "
    f"names to offer, and never choose between them yourself. Use {MORE} before "
    "spending another page on a long answer, saying how much you have shown and how "
    "much there is.\n"
    "\n"
    "Answers arrive one page at a time and report a total; read further only with the "
    "offset the last answer gave you. A tool that counts is worth more than a tool "
    "called twenty times: when the question is how many there are, ask for the total "
    "rather than paging to the end of the list. Look a name up as it was said to "
    "you: narrowing to one sort of thing before the tools have told you a name "
    "answers to several is settling a question that was never yours. A name spelt "
    "wrong is still the name you were given, so look that up rather than the one you "
    "think was meant, however plain the correction looks. When nothing answers to it, "
    "settle which sort of thing it is with whoever asked, ask the wiki for the real "
    "names closest to it, and put those back to them.\n"
    "\n"
    "You are writing for a player, not for another program. Never put a ref, an id, a "
    "map coordinate, a plane, a region or a track number in front of them: they mean "
    "nothing to a person and they are not what was asked. Two things with one name "
    "and nothing to tell them apart are one thing as far as the answer goes, so say "
    "how many of them there are and answer for all of them at once, rather than "
    "asking which numbered one was meant.\n"
    "\n"
    f"{FORMAT}"
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
        "--report",
        "--log",
        dest="report",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "write this run to FILE as a markdown report, replacing it, and keep the "
            "terminal to a status line"
        ),
    )
    return declared


def reaching(wiki: Wiki) -> StdioTransport:
    """A wiki of this probe's own, started here and spoken to down a pipe."""
    return wiki.transport()


def backoff(spent: int) -> float:
    """How long to leave the api alone when it did not say, growing each time."""
    return min(FIRST_WAIT * 2.0**spent, LONGEST_WAIT)


def asked_for(headers: httpx.Headers, spent: int) -> float:
    """How long the api asked to be left alone, or a growing wait if it did not say."""
    said = headers.get("retry-after")
    try:
        return min(max(float(said or ""), 0.0), LONGEST_WAIT)
    except ValueError:
        return backoff(spent)


class Paced(httpx.AsyncHTTPTransport):
    """Wait a held-back request out, rather than failing a probe or going quiet."""

    def __init__(self, screen: Screen, most: int = MOST_WAITS) -> None:
        super().__init__()
        self.screen = screen
        self.most = most
        self.scope: anyio.CancelScope | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for spent in range(self.most + 1):
            last = spent == self.most
            try:
                answered = await super().handle_async_request(request)
            except httpx.TimeoutException:
                if last:
                    raise
                waited = f"the api took over {took(THINKING)} to answer"
                await self.waiting(backoff(spent), waited)
                continue
            if answered.status_code not in HELD_BACK or last:
                return answered
            await answered.aread()
            await answered.aclose()
            await self.waiting(
                asked_for(answered.headers, spent),
                f"the api answered {answered.status_code} and is holding this run back",
            )
        raise AssertionError("unreachable: the last time round always answers")

    async def waiting(self, seconds: float, why: str) -> None:
        """Leave the api alone that long, out loud and not at the probe's expense."""
        self.screen.note(f"{why}; asking again in {took(seconds)}")
        if self.scope is not None:
            self.scope.deadline += seconds
        await anyio.sleep(seconds)


async def watched(screen: Screen, lag: float = STALL) -> None:
    """Report whenever this process stops attending to its own work."""
    while True:
        started = time.monotonic()
        await asyncio.sleep(0.5)
        stalled = time.monotonic() - started - 0.5
        if stalled > lag:
            screen.note(f"this run stopped attending to itself for {stalled:.1f}s")


async def ticking(screen: Screen, every: float = REDRAW) -> None:
    """Keep whatever the terminal is showing moving while a probe thinks."""
    while True:
        await asyncio.sleep(every)
        screen.tick()


def subscribed() -> bool:
    """Whether this run signs in with a subscription token rather than an api key."""
    return bool(os.environ.get(TOKEN_VARIABLE))


def model(paced: Paced) -> tuple[AnthropicModel, AsyncAnthropic]:
    """The model, signed in with whichever credential this run was given."""
    token = os.environ.get(TOKEN_VARIABLE)
    reached = httpx.AsyncClient(transport=paced, timeout=httpx.Timeout(THINKING))
    client = (
        AsyncAnthropic(
            auth_token=token,
            default_headers={"anthropic-beta": OAUTH_BETA},
            http_client=reached,
            max_retries=0,
            timeout=THINKING,
        )
        if token
        else AsyncAnthropic(http_client=reached, max_retries=0, timeout=THINKING)
    )
    made = AnthropicModel(MODEL, provider=AnthropicProvider(anthropic_client=client))
    return made, client


def identity() -> str | tuple[()]:
    """The first block of the system prompt, when there has to be one."""
    return CLAUDE_CODE if subscribed() else ()


def asking(
    given: Iterator[str], scripted: bool, notes: Notes, screen: Screen
) -> tuple[Callable[..., str], ...]:
    """The four ways the model may turn back to whoever asked."""

    def answered(tool: str, question: str, detail: Sequence[str], standing: str) -> str:
        offered = next(given, None)
        source = (
            "scripted" if offered is not None else "standing" if scripted else "typed"
        )
        ask = Ask(tool=tool, question=question, detail=tuple(detail), source=source)
        screen.asking(ask)
        if source == "typed":
            offered = screen.types()
        elif source == "standing":
            offered = standing
        ask.answer = (offered or standing).strip()
        notes.events.append(ask)
        screen.answered(ask)
        return ask.answer

    def ask_to_clarify(question: str) -> str:
        """Ask for the missing part of a question too vague to look anything up for."""
        return answered(CLARIFY, question, (), FALLBACK)

    def ask_to_confirm(question: str, proposal: str) -> str:
        """Check a reading of the question with whoever asked before acting on it."""
        return answered(CONFIRM, question, (f"proposing: {proposal}",), YES)

    def ask_to_choose(question: str, options: list[str]) -> str:
        """Put candidates to whoever asked and use the one they pick, never your own."""
        first = f"{FIRST}, {options[0]}" if options else FIRST
        return answered(CHOOSE, question, tuple(options), first)

    def ask_for_more(question: str, shown: int, total: int) -> str:
        """Ask whether to read on, saying how much is shown and how much there is."""
        return answered(MORE, question, (f"shown {shown} of {total}",), YES)

    return (ask_to_clarify, ask_to_confirm, ask_to_choose, ask_for_more)


def steps(messages: Sequence[ModelMessage]) -> list[str]:
    """Every tool the model called, in the order it called them."""
    return [
        part.tool_name
        for message in messages
        for part in message.parts
        if isinstance(part, ToolCallPart)
    ]


def spoken(messages: Sequence[ModelMessage]) -> str:
    """Everything the model told the person, not only its closing answer."""
    return "\n".join(
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, TextPart)
    )


def checked(
    probe: Probe, called: Sequence[str], said: str, spoke: str = ""
) -> list[tuple[str, str]]:
    """Say whether this probe showed what it is here to show, a line per expectation.

    `said` is the final answer; `spoke` is everything the model told the person.
    """
    from_wiki = [tool for tool in called if tool not in ASK_TOOLS]
    asked = [tool for tool in called if tool in ASK_TOOLS]
    spoken = (spoke or said).lower()
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

    for wanted in probe.calls:
        if wanted in from_wiki:
            lines.append(
                (WORKED, f"it followed the link this probe is here for: {wanted}")
            )
        else:
            lines.append(
                (
                    UNSURE,
                    f"it answered without ever calling {wanted}, which this covers",
                )
            )

    unwelcome = [tool for tool in asked if tool not in probe.may_ask]
    if unwelcome and not probe.human_turn:
        lines.append(
            (UNSURE, f"it asked when it did not have to: {', '.join(unwelcome)}")
        )

    for wanted in probe.says:
        if wanted.lower() in spoken:
            lines.append((WORKED, f"the answer carries {wanted!r}"))
        else:
            lines.append((UNSURE, f"the answer never mentions {wanted!r}"))

    denied = [one for one in probe.never_says if one.lower() in spoken]
    if denied:
        lines.append(
            (MISSED, f"it says the wiki holds nothing, and it does: {denied[0]!r}")
        )

    if probe.says_any and not any(one.lower() in spoken for one in probe.says_any):
        lines.append((UNSURE, "the answer does not admit the gap it was asked about"))
    elif probe.says_any:
        lines.append((WORKED, "the answer says the wiki does not hold this"))

    lines.append(_addressing(spoke or said))
    return lines


def _addressing(said: str) -> tuple[str, str]:
    """Say whether the answer put the game's own bookkeeping in front of a person."""
    shown = list(dict.fromkeys(ADDRESSING.findall(said)))
    if not shown:
        return (WORKED, "the answer names things rather than numbering them")
    written = ", ".join(repr(one) for one in shown[:MOST_ADDRESSING])
    if len(shown) > MOST_ADDRESSING:
        written = f"{written} and {len(shown) - MOST_ADDRESSING} more"
    return (MISSED, f"the answer shows what only the game uses: {written}")


async def offered_by(wiki: Wiki) -> list[str]:
    """Every tool the running wiki puts in front of a client, under its own name."""
    async with Client(reaching(wiki)) as client:
        return sorted(tool.name for tool in await client.list_tools())


async def run(
    probe: Probe,
    wiki: Wiki,
    given: Iterator[str],
    scripted: bool,
    screen: Screen,
    where: tuple[int, int],
    made: AnthropicModel,
    paced: Paced,
) -> Notes:
    """Put one probe, keeping every step it takes, and say whether it showed what it
    should.
    """
    notes = Notes(probe=probe)
    agent = Agent(
        made,
        output_type=str,
        toolsets=[MCPToolset(reaching(wiki))],
        system_prompt=identity(),
        instructions=PROMPT,
    )
    for reaching_back in asking(given, scripted, notes, screen):
        agent.tool_plain(reaching_back)

    index, total = where
    screen.starting(index, total, probe)
    started = time.monotonic()
    try:
        async with agent:
            with anyio.fail_after(PATIENCE) as thinking:
                paced.scope = thinking
                answered = await stepped(agent, probe.question, notes, screen)
    except TimeoutError:
        notes.broke = (
            f"this probe was given up on after {took(PATIENCE)}, with the steps "
            "above as all it had reached"
        )
    except Exception as broke:
        notes.broke = f"this probe came apart: {type(broke).__name__}: {broke}"
    else:
        notes.called = steps(answered.all_messages())
        notes.said = answered.output
        notes.checks = checked(
            probe, notes.called, answered.output, spoken(answered.all_messages())
        )
        notes.worked = all(outcome == WORKED for outcome, _ in notes.checks)
    finally:
        paced.scope = None
    notes.seconds = time.monotonic() - started
    screen.settled(notes)
    return notes


async def stepped(
    agent: Agent[None, str], question: str, notes: Notes, screen: Screen
) -> AgentRunResult[str]:
    """Put one question, keeping each step at the moment it is taken."""
    async with agent.iter(question) as walking:
        async for node in walking:
            if not Agent.is_call_tools_node(node):
                continue
            parts = node.model_response.parts
            if not any(isinstance(part, ToolCallPart) for part in parts):
                continue
            for part in parts:
                if isinstance(part, TextPart) and part.content.strip():
                    notes.events.append(Said(part.content))
                    screen.spoke(part.content)
                elif isinstance(part, ToolCallPart) and part.tool_name not in ASK_TOOLS:
                    call = Call(part.tool_name, part.args)
                    notes.events.append(call)
                    screen.called(call)
    answered = walking.result
    if answered is None:
        raise RuntimeError("the model stopped without answering")
    return answered


def coverage(offered: Sequence[str], reached: Counter[str]) -> list[str]:
    """Which of the wiki's own tools this sweep ever exercised."""
    touched = [name for name in offered if reached.get(name)]
    untouched = [name for name in offered if not reached.get(name)]
    lines = [f"\n  tool coverage: {len(touched)} of {len(offered)} the wiki offers"]
    if untouched:
        lines.append("    never called by any probe:")
        lines += [f"      {name}" for name in untouched]
    return lines


def summarise(
    outcomes: Sequence[tuple[str, bool]], asks: Counter[str], seconds: float
) -> tuple[list[str], int]:
    """How the sweep went, and what this process should exit with."""
    worked = [tag for tag, ok in outcomes if ok]
    fell_short = [tag for tag, ok in outcomes if not ok]
    lines = [
        f"\n  probes: {len(worked)} of {len(outcomes)} showed everything asked of "
        f"them, in {took(seconds)}"
    ]
    if fell_short:
        lines.append(f"    fell short: {', '.join(fell_short)}")
    if asks:
        turns = ", ".join(f"{name} x{count}" for name, count in sorted(asks.items()))
        lines.append(f"  human turns: {turns}")
    else:
        lines.append(
            "  human turns: none, which for this sweep is a failure of its own"
        )
    return lines, 0 if not fell_short else 1


def chosen(only: Sequence[str] | None) -> tuple[Probe, ...]:
    """The probes this run puts, and nothing else."""
    if not only:
        return PROBES
    wanted = set(only)
    return tuple(probe for probe in PROBES if probe.tag in wanted)


def written(where: Path, probes: Sequence[Probe]) -> Document:
    """The document this run fills in, before there is anything to write in it."""
    return Document(where=where, started=datetime.now(), total=len(probes))


async def _main(
    probes: Sequence[Probe], scripted: bool, screen: Screen, document: Document | None
) -> int:
    with served() as wiki:
        offered = await offered_by(wiki)
        opening = [
            f"  the wiki is answering down a pipe as `{wiki.spawned}`, "
            f"reading {dataset()}",
            f"  it offers {len(offered)} tools, and this sweep puts "
            f"{len(probes)} questions",
        ]
        for line in opening:
            print(line)
        if document is not None:
            document.fact("model", f"`{MODEL}`")
            document.fact("dataset", f"`{dataset()}`")
            document.fact("wiki", f"{len(offered)} tools, started as `{wiki.spawned}`")
            document.fact("probes", str(len(probes)))
            document.fact(
                "answers", "scripted" if scripted else "typed at the terminal"
            )
            document.save()

        paced = Paced(screen)
        made, signed_in = model(paced)
        watching = asyncio.create_task(watched(screen))
        drawing = asyncio.create_task(ticking(screen))
        reached: Counter[str] = Counter()
        asks: Counter[str] = Counter()
        outcomes: list[tuple[str, bool]] = []
        started = time.monotonic()
        try:
            for index, probe in enumerate(probes, start=1):
                given = iter(probe.answers if scripted else ())
                notes = await run(
                    probe,
                    wiki,
                    given,
                    scripted,
                    screen,
                    (index, len(probes)),
                    made,
                    paced,
                )
                outcomes.append((probe.tag, notes.worked))
                reached.update(notes.called)
                asks.update(name for name in notes.called if name in ASK_TOOLS)
                if document is not None:
                    document.add(notes)
        finally:
            watching.cancel()
            drawing.cancel()
            await signed_in.close()

        seconds = time.monotonic() - started
        if document is not None:
            document.close(offered, reached, asks, seconds)
        closing, code = summarise(outcomes, asks, seconds)
        screen.finished([*coverage(offered, reached), *closing])
        return code


def listed() -> None:
    """Print every probe and what it is here to cover, without asking anything."""
    for probe in PROBES:
        print(f"  {probe.tag:18} {probe.covers}")


def main() -> None:
    """Run the sweep, typed at or scripted, into a document if one was named."""
    read_env(HERE)
    asked = parser().parse_args()
    code = _sweep(asked)
    if asked.report is not None:
        print(f"\n  this run was written to {asked.report}")
    raise SystemExit(code)


def _sweep(asked: argparse.Namespace) -> int:
    local_data()

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

    document = written(asked.report, probes) if asked.report is not None else None
    screen: Screen = Loud() if document is None else Bar(len(probes))
    return asyncio.run(_main(probes, asked.scripted, screen, document))


if __name__ == "__main__":
    main()
