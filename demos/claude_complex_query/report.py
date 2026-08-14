"""Write one sweep down as a document worth scanning, and keep the terminal to a
status line while it is being written.
"""

from __future__ import annotations

import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from claude_common import MISSED, UNSURE, WORKED, told

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from datetime import datetime
    from pathlib import Path
    from typing import TextIO

    from claude_complex_query.probes import Probe

#: How each checked expectation is marked in the document.
MARKS = {WORKED: "\u2705", UNSURE: "\u26a0\ufe0f", MISSED: "\u274c"}

#: Where an answer to one of the model's questions came from.
SOURCES = {
    "scripted": "the probe's own answer",
    "standing": "the standing answer, unasked",
    "typed": "typed at the terminal",
}

STANDING = {True: "passed", False: "fell short"}
LEGEND = (
    f"{MARKS[WORKED]} showed everything asked of it, "
    f"{MARKS[UNSURE]} fell short of something, "
    f"{MARKS[MISSED]} came apart, or said the wiki holds nothing where it does"
)
INDEX = "[back to the table](#at-a-glance)"
LEAST_TICKS = 4
RULE = "=" * 78
BACKTICKS = re.compile(r"`+")


def took(seconds: float) -> str:
    """A length of time as a reader says it."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}m {rest:02d}s"


def cell(text: str) -> str:
    """One table cell, with anything that would end it early kept inside."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def fence(text: str) -> str:
    """The shortest run of backticks that can hold this text,
    never fewer than four."""
    longest = max((len(run) for run in BACKTICKS.findall(text)), default=0)
    return "`" * max(LEAST_TICKS, longest + 1)


def quoted(lines: Iterable[str]) -> list[str]:
    """Those lines, as one markdown quotation."""
    return [f"> {line}".rstrip() for line in lines]


def arguments(args: Any) -> str:
    """What a tool was passed, as it would be written out."""
    if isinstance(args, dict):
        return ", ".join(f"{name}={value!r}" for name, value in args.items())
    if args in (None, ""):
        return ""
    return str(args)


@dataclass
class Call:
    """One tool the model called, and what it passed."""

    tool: str
    args: Any

    def written(self) -> str:
        """The call as one line."""
        return f"{self.tool}({arguments(self.args)})"


@dataclass
class Said:
    """Something the model said while it was still working."""

    words: str


@dataclass
class Ask:
    """One turn back to the person who asked, and what came back."""

    tool: str
    question: str
    detail: tuple[str, ...] = ()
    answer: str = ""
    source: str = "typed"


Event = Call | Said | Ask


@dataclass
class Notes:
    """Everything one probe did, in the order it did it."""

    probe: Probe
    events: list[Event] = field(default_factory=list)
    called: list[str] = field(default_factory=list)
    said: str = ""
    checks: list[tuple[str, str]] = field(default_factory=list)
    seconds: float = 0.0
    broke: str = ""
    worked: bool = False

    @property
    def steps(self) -> int:
        """How many tools this probe spent, asking and reading alike."""
        if self.called:
            return len(self.called)
        return sum(1 for event in self.events if isinstance(event, Call | Ask))

    @property
    def mark(self) -> str:
        """How this probe reads at a glance."""
        if self.broke:
            return MARKS[MISSED]
        return MARKS[WORKED] if self.worked else MARKS[UNSURE]

    @property
    def standing(self) -> str:
        """Whether this probe showed what it is here to show, in a word."""
        if self.broke:
            return "came apart"
        return STANDING[self.worked]


class Screen:
    """What the terminal is told while a sweep runs."""

    def starting(self, index: int, total: int, probe: Probe) -> None:
        """A probe is about to be put."""

    def called(self, call: Call) -> None:
        """The model reached for a tool."""

    def spoke(self, words: str) -> None:
        """The model said something on its way to an answer."""

    def asking(self, ask: Ask) -> None:
        """The model turned back to the person who asked."""

    def types(self) -> str:
        """Read the answer to that question off the terminal."""
        try:
            return input("  your answer: ").strip()
        except EOFError:
            return ""

    def answered(self, ask: Ask) -> None:
        """That question was answered."""

    def settled(self, notes: Notes) -> None:
        """A probe is over, and this is everything it did."""

    def note(self, words: str) -> None:
        """Something worth saying that belongs to no probe."""

    def tick(self) -> None:
        """Time has passed and nothing else has happened."""

    def finished(self, lines: Sequence[str]) -> None:
        """The sweep is over, and this is how it went."""
        for line in lines:
            print(line)


class Loud(Screen):
    """Every step of every probe, printed as it happens, for a run with no document."""

    def starting(self, index: int, total: int, probe: Probe) -> None:
        print(f"\n{RULE}")
        print(f"  [{index}/{total}] {probe.tag}: {probe.covers}")
        print(f"  asked: {probe.question}")

    def called(self, call: Call) -> None:
        print(f"    called {call.written()}", flush=True)

    def spoke(self, words: str) -> None:
        print(f"    it says: {words.strip()}", flush=True)

    def asking(self, ask: Ask) -> None:
        print(f"\n  the model asks: {ask.question}")
        for line in ask.detail:
            print(f"    - {line}")

    def answered(self, ask: Ask) -> None:
        if ask.source != "typed":
            print(f"  your answer: {ask.answer}   ({SOURCES[ask.source]})")

    def settled(self, notes: Notes) -> None:
        if notes.broke:
            print(f"\n  {notes.broke}")
            return
        print(f"\n  said: {notes.said.strip()}")
        print(f"  that took {took(notes.seconds)} and {notes.steps} step(s)")
        print("\n  what happened:")
        for outcome, note in notes.checks:
            print(told(outcome, note))

    def note(self, words: str) -> None:
        print(f"    ({words})")


class Bar(Screen):
    """One line saying where the run has reached, for a run being written down."""

    def __init__(self, total: int, out: TextIO | None = None) -> None:
        self.total = total
        self.out = out or sys.stdout
        self.live = self.out.isatty()
        self.begun = time.monotonic()
        self.at = self.begun
        self.index = 0
        self.tag = ""
        self.marks: list[str] = []

    def starting(self, index: int, total: int, probe: Probe) -> None:
        self.index, self.total, self.tag = index, total, probe.tag
        self.at = time.monotonic()
        self.tick()

    def tick(self) -> None:
        if not self.live or not self.tag:
            return
        width = shutil.get_terminal_size((80, 24)).columns
        line = (
            f"  [{self.index:>2}/{self.total}] {self.tag}  "
            f"{took(time.monotonic() - self.at)}  {self._score()}  "
            f"elapsed {took(time.monotonic() - self.begun)}"
        )
        self.out.write(f"\r\x1b[2K{line[: width - 1]}")
        self.out.flush()

    def clear(self) -> None:
        """Take the line back off the terminal, so something else can be printed."""
        if self.live:
            self.out.write("\r\x1b[2K")
            self.out.flush()

    def asking(self, ask: Ask) -> None:
        if ask.source != "typed":
            return
        self.clear()
        print(f"\n  the model asks: {ask.question}", file=self.out)
        for line in ask.detail:
            print(f"    - {line}", file=self.out)

    def answered(self, ask: Ask) -> None:
        if ask.source == "typed":
            self.tick()

    def settled(self, notes: Notes) -> None:
        self.clear()
        self.tag = ""
        self.marks.append(notes.mark)
        print(
            f"  {notes.mark} {notes.probe.tag:<22}{notes.steps:>3} steps"
            f"{took(notes.seconds):>8}   {notes.standing}",
            file=self.out,
            flush=True,
        )

    def note(self, words: str) -> None:
        self.clear()
        print(f"    ({words})", file=self.out, flush=True)
        self.tick()

    def finished(self, lines: Sequence[str]) -> None:
        self.tag = ""
        self.clear()
        for line in lines:
            print(line, file=self.out)

    def _score(self) -> str:
        """How the probes behind this one went, in three counts."""
        return "  ".join(f"{mark} {self.marks.count(mark)}" for mark in MARKS.values())


@dataclass
class Document:
    """The sweep as a markdown document, rewritten whole after every probe."""

    where: Path
    started: datetime
    total: int
    facts: list[tuple[str, str]] = field(default_factory=list)
    sections: list[Notes] = field(default_factory=list)
    offered: tuple[str, ...] = ()
    reached: Mapping[str, int] = field(default_factory=dict)
    asks: Mapping[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    over: bool = False

    def fact(self, name: str, value: str) -> None:
        """One thing worth knowing about the run before reading any of it."""
        self.facts.append((name, value))

    def add(self, notes: Notes) -> None:
        """Keep what a probe did, and write the document out as it now stands."""
        self.sections.append(notes)
        self.save()

    def close(
        self,
        offered: Sequence[str],
        reached: Mapping[str, int],
        asks: Mapping[str, int],
        seconds: float,
    ) -> None:
        """Say how the whole sweep went, and write the finished document."""
        self.offered = tuple(offered)
        self.reached = dict(reached)
        self.asks = dict(asks)
        self.seconds = seconds
        self.over = True
        self.save()

    def save(self) -> None:
        """Write everything held so far over whatever is at that path."""
        self.where.parent.mkdir(parents=True, exist_ok=True)
        self.where.write_text(self._written(), encoding="utf-8")

    def _written(self) -> str:
        lines = [*self._head(), *self._glance(), *self._coverage(), *self._turns()]
        for notes in self.sections:
            lines += _section(notes)
        return "\n".join(lines).rstrip() + "\n"

    def _head(self) -> list[str]:
        when = self.started.strftime("%Y-%m-%d %H:%M")
        lines = [
            "# Complex query sweep",
            "",
            "*Questions of every shape this wiki can be asked, put to one model, "
            "with everything it read and everything it said.*",
            "",
            f"`{when}`",
            "",
            "|  |  |",
            "| --- | --- |",
        ]
        lines += [f"| **{name}** | {cell(value)} |" for name, value in self.facts]
        return [*lines, ""]

    def _glance(self) -> list[str]:
        worked = sum(1 for notes in self.sections if notes.worked)
        short = [
            notes.probe.tag
            for notes in self.sections
            if not notes.worked and not notes.broke
        ]
        broke = [notes.probe.tag for notes in self.sections if notes.broke]
        standing = (
            f"**{worked} of {len(self.sections)}** probes showed everything asked of "
            f"them, in {took(self.seconds)}."
            if self.over
            else f"**{len(self.sections)} of {self.total}** put so far. This run has "
            "not finished."
        )
        lines = ["## At a glance", "", standing, ""]
        if self.over and short:
            lines += [f"Fell short: {_tags(short)}.", ""]
        if self.over and broke:
            lines += [f"Came apart: {_tags(broke)}.", ""]
        lines += [
            "|  | probe | steps | took | what it covers |",
            "| :-: | --- | --: | --: | --- |",
        ]
        lines += [
            f"| {notes.mark} | [{notes.probe.tag}](#{_anchor(notes.probe.tag)}) "
            f"| {notes.steps} | {took(notes.seconds)} | {cell(notes.probe.covers)} |"
            for notes in self.sections
        ]
        return [*lines, "", f"<sub>{LEGEND}</sub>", ""]

    def _coverage(self) -> list[str]:
        if not self.offered:
            return []
        touched = [name for name in self.offered if self.reached.get(name)]
        untouched = [name for name in self.offered if not self.reached.get(name)]
        lines = [
            "### Tool coverage",
            "",
            f"**{len(touched)} of {len(self.offered)}** tools the wiki offers were "
            "called at least once.",
            "",
        ]
        if untouched:
            called = ", ".join(f"`{name}`" for name in untouched)
            lines += [f"Never called by any probe: {called}.", ""]
        return lines

    def _turns(self) -> list[str]:
        if not self.over:
            return []
        if not self.asks:
            return [
                "### Turns back to you",
                "",
                "None, which for this sweep is a failure of its own.",
                "",
            ]
        lines = ["### Turns back to you", "", "| tool | times |", "| --- | --: |"]
        lines += [
            f"| `{name}` | {count} |" for name, count in sorted(self.asks.items())
        ]
        return [*lines, ""]


def _tags(tags: Sequence[str]) -> str:
    """Several probes, named the way one is."""
    return ", ".join(f"`{tag}`" for tag in tags)


def _anchor(tag: str) -> str:
    """Where a probe's own heading sits in the finished document."""
    return tag.lower().replace(" ", "-")


def _section(notes: Notes) -> list[str]:
    """One probe, from the question to what its answer proved."""
    probe = notes.probe
    lines = [
        "---",
        "",
        f"## {probe.tag}",
        "",
        f"*{probe.covers}*",
        "",
        f"{notes.mark} **{notes.standing}** in {took(notes.seconds)} "
        f"over {notes.steps} step(s)",
        "",
        *quoted([f"**Asked** {probe.question}"]),
        "",
    ]
    lines += _transcript(notes.events)
    if notes.broke:
        lines += [*quoted([f"**Came apart** {notes.broke}"]), ""]
    if notes.said.strip():
        ticks = fence(notes.said)
        lines += [
            "**What it said**",
            "",
            f"{ticks}markdown",
            notes.said.strip(),
            ticks,
            "",
        ]
    lines += _checks(notes.checks)
    return [*lines, f"<sub>{INDEX}</sub>", ""]


def _transcript(events: Sequence[Event]) -> list[str]:
    """Every call and every turn back, in the order they happened."""
    lines: list[str] = []
    calls: list[str] = []

    def flush() -> None:
        if calls:
            lines.extend(["```text", *calls, "```", ""])
            calls.clear()

    for event in events:
        if isinstance(event, Call):
            calls.append(event.written())
            continue
        flush()
        if isinstance(event, Said):
            lines += [*quoted(_narration(event.words)), ""]
        else:
            lines += _ask(event)
    flush()
    return ["**What it did**", "", *lines] if lines else []


def _narration(words: str) -> list[str]:
    """What the model said between one call and the next, set apart from its answer."""
    return [
        f"*{line}*" if line.strip() else line for line in words.strip().splitlines()
    ]


def _ask(ask: Ask) -> list[str]:
    """One question the model put to the person, and the answer it was given."""
    body = [f"**It asked you** (`{ask.tool}`)", ""]
    body += ask.question.strip().splitlines()
    if ask.detail:
        body += ["", *[f"- {one}" for one in ask.detail]]
    body += ["", f"**You answered** *{SOURCES[ask.source]}*", "", ask.answer]
    return [*quoted(body), ""]


def _checks(checks: Sequence[tuple[str, str]]) -> list[str]:
    """What the probe asked of the answer, and which of it held."""
    if not checks:
        return []
    lines = ["**What happened**", "", "|  |  |", "| :-: | --- |"]
    lines += [f"| {MARKS[outcome]} | {cell(note)} |" for outcome, note in checks]
    return [*lines, ""]
