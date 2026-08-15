"""Gather what every demonstration here needs before it can ask Claude anything."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from fastmcp.client.transports import StdioTransport

from wiki_api.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Generator

DEMOS = Path(__file__).resolve().parent
ROOT = DEMOS.parent
MCP_CONFIG = ROOT / ".mcp.json"
ENV_NAME = ".env"

TOKEN_VARIABLE = "CLAUDE_CODE_OAUTH_TOKEN"
KEY_VARIABLE = "ANTHROPIC_API_KEY"
CREDENTIALS = (TOKEN_VARIABLE, KEY_VARIABLE, "ANTHROPIC_AUTH_TOKEN")
SIGNED_IN = Path.home() / ".claude" / ".credentials.json"

CONSOLE_SCRIPT = "scape2009-wiki-mcp"
SERVER_MODULE = "wiki_api.surfaces.mcp.server"

FULL_DATA = "data"
DATA_VARIABLE = "WIKI_API_DATA_DIR"
SERVER_LOG = "wiki.log"

OAUTH_BETA = "oauth-2025-04-20"
CLAUDE_CODE = "You are Claude Code, Anthropic's official CLI for Claude."

WORKED = "WORKED"
MISSED = "MISSED"
UNSURE = "UNSURE"


def env_of(folder: Path) -> Path:
    """Locate the .env a demonstration keeps its credential and settings in."""
    return folder / ENV_NAME


def read_env(folder: Path) -> None:
    """Read that file, so one demonstration's settings do not leak into another."""
    load_dotenv(env_of(folder))


def local_data(data_dir: str = FULL_DATA) -> str:
    """Pin this run to the knowledge base built in this checkout."""
    os.environ[DATA_VARIABLE] = data_dir
    return data_dir


def wanted_env(folder: Path) -> str:
    """Write what belongs in that file, for a reader who has not made one."""
    return f"""no {ENV_NAME} beside this demonstration. Create {env_of(folder)} with:

    {TOKEN_VARIABLE}=

That signs in to Anthropic so there is a model to ask. Generate it with
`claude setup-token`, which uses your Claude subscription rather than pay-per-token
api credits, or put an {KEY_VARIABLE} there instead.

Nothing else belongs there. The wiki is started by this demonstration as a process of
its own, spoken to down a pipe, and reads the knowledge base in {FULL_DATA}: it is
reachable by nothing but its parent, so it issues no key and asks for none."""


def credential() -> str | None:
    """Name the variable this run signs in to Anthropic with, if any."""
    return next((name for name in CREDENTIALS if os.environ.get(name)), None)


def server_command() -> tuple[str, list[str]]:
    """How to start the wiki: its console script, else the module behind it."""
    console = Path(sys.executable).with_name(CONSOLE_SCRIPT)
    if console.exists():
        return str(console), []
    return sys.executable, ["-m", SERVER_MODULE]


@dataclass(frozen=True)
class Wiki:
    """The wiki as a local process, and what it takes to be answered by it."""

    command: str
    arguments: tuple[str, ...]
    settings: dict[str, str]
    cwd: str
    data_dir: str
    log: Path

    @property
    def spawned(self) -> str:
        """The command a client runs to have a wiki of its own, as typed."""
        return " ".join([Path(self.command).name, *self.arguments])

    @property
    def environment(self) -> dict[str, str]:
        """The whole environment to start the wiki in, this run's settings on top.

        Spawning it replaces the environment rather than adding to it, so what the
        interpreter needs to run at all has to be carried across as well.
        """
        return {**os.environ, **self.settings}

    def transport(self) -> StdioTransport:
        """A wiki of one client's own, living exactly as long as that client.

        `keep_alive` is off so the process ends with the connection rather than
        outliving the question it was started for.
        """
        return StdioTransport(
            command=self.command,
            args=list(self.arguments),
            env=self.environment,
            cwd=self.cwd,
            keep_alive=False,
            log_file=self.log,
        )

    def spoken(self) -> str:
        """Everything the wiki has written to its error stream so far."""
        if not self.log.exists():
            return ""
        return self.log.read_text(encoding="utf-8", errors="replace")


@contextmanager
def served(*, data_dir: str = FULL_DATA) -> Generator[Wiki]:
    """Hand out a local wiki for the length of one demonstration."""
    command, arguments = server_command()
    settings = {
        "WIKI_API_MCP_TRANSPORT": "stdio",
        "WIKI_API_AUTH_MODE": "off",
        DATA_VARIABLE: data_dir,
    }
    with TemporaryDirectory() as kept:
        yield Wiki(
            command=command,
            arguments=tuple(arguments),
            settings=settings,
            cwd=str(ROOT),
            data_dir=data_dir,
            log=Path(kept) / SERVER_LOG,
        )


def dataset() -> Path:
    """The artifact the settings point at, whether or not it is there yet."""
    return get_settings().artifact_path


def unready(folder: Path, *, signed_in_counts: bool = True) -> str | None:
    """Say what stands between this demonstration and a working run, or nothing.

    `signed_in_counts` is for a demonstration that shells out to `claude`, which can
    use whoever this machine is already signed in as.
    """
    if not env_of(folder).exists():
        return wanted_env(folder)
    artifact = dataset()
    if not artifact.exists():
        return (
            f"no knowledge base at {artifact}: run `uv run poe build-artifact "
            "<documents>` to build one. These demonstrations read the build in "
            f"{FULL_DATA} and nothing else, so building it elsewhere will not do"
        )
    if credential() is not None:
        return None
    if signed_in_counts and SIGNED_IN.exists():
        return None
    put = f"Put a token in {env_of(folder)}"
    if signed_in_counts:
        return f"no way to sign in. {put}, or run `claude` once"
    return (
        f"no way to sign in. {put}: this demonstration reaches the api itself, so it "
        f"needs {TOKEN_VARIABLE} or {KEY_VARIABLE} spelt out, and cannot borrow "
        "whoever `claude` on this machine is signed in as"
    )


def told(outcome: str, note: str) -> str:
    """One checked expectation, in the words every demonstration here uses."""
    return f"    {outcome}  {note}"
