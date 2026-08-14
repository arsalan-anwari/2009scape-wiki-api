"""Gather what every demonstration here needs before it can ask Claude anything."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryFile
from typing import IO, TYPE_CHECKING

from dotenv import load_dotenv

from wiki_api.access import (
    Credential,
    credential_from_file,
    find_token,
)
from wiki_api.access.paths import config_dir, tokens_dir
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

WIKI_TOKEN_FILE_VARIABLE = "DEMO_TOKEN_FILE"
WIKI_LABEL = "demos"
CONSOLE_SCRIPT = "scape2009-wiki-mcp"
SERVER_MODULE = "wiki_api.surfaces.mcp.server"
TEST_DATA = "data/tests"
LOCALHOST = "127.0.0.1"
MOST_WAIT = 30.0

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


def wanted_env(folder: Path) -> str:
    """Write what belongs in that file, for a reader who has not made one."""
    return f"""no {ENV_NAME} beside this demonstration. Create {env_of(folder)} with:

    {TOKEN_VARIABLE}=

That signs in to Anthropic so there is a model to ask. Generate it with
`claude setup-token`, which uses your Claude subscription rather than pay-per-token
api credits, or put an {KEY_VARIABLE} there instead.

The key this wiki issued takes no line here: issue it with `uv run poe keys issue
--label {WIKI_LABEL}` beforehand and it is read from the file that keeps, or name
another with a {WIKI_TOKEN_FILE_VARIABLE} line. Any WIKI_API_ setting put in the same
{ENV_NAME} is picked up too."""


def credential() -> str | None:
    """Name the variable this run signs in to Anthropic with, if any."""
    return next((name for name in CREDENTIALS if os.environ.get(name)), None)


def wiki_credential() -> Credential | None:
    """Read the key this run presents to the wiki.

    The file `poe keys issue --label demos` keeps, unless DEMO_TOKEN_FILE names another.
    """
    named = os.environ.get(WIKI_TOKEN_FILE_VARIABLE)
    if named:
        return credential_from_file(Path(named).expanduser())
    kept = find_token(config_dir(), WIKI_LABEL)
    return credential_from_file(kept) if kept is not None else None


@dataclass(frozen=True)
class Wiki:
    """A running wiki, and what it takes to be answered by it."""

    url: str
    headers: dict[str, str]
    key_id: str
    kept: str


def server_command() -> tuple[str, list[str]]:
    """How to start the wiki: its console script, else the module behind it."""
    console = Path(sys.executable).with_name(CONSOLE_SCRIPT)
    if console.exists():
        return str(console), []
    return sys.executable, ["-m", SERVER_MODULE]


def free_port() -> int:
    """Pick a port nothing is listening on, for a server lasting one run."""
    with closing(socket.socket()) as held:
        held.bind((LOCALHOST, 0))
        port: int = held.getsockname()[1]
    return port


@contextmanager
def served(*, data_dir: str = TEST_DATA, wait: float = MOST_WAIT) -> Generator[Wiki]:
    """Run the wiki over http for the length of one demonstration."""
    held = wiki_credential()
    if held is None:
        raise RuntimeError(f"no key to present to the wiki, see {WIKI_LABEL}")
    port = free_port()
    command, arguments = server_command()
    environment = {
        **os.environ,
        "WIKI_API_MCP_TRANSPORT": "http",
        "WIKI_API_MCP_HOST": LOCALHOST,
        "WIKI_API_MCP_PORT": str(port),
        "WIKI_API_AUTH_MODE": "required",
    }
    environment.setdefault("WIKI_API_DATA_DIR", data_dir)
    # Into a file rather than a pipe: the wiki logs a line per request and nothing here
    # reads it back until something goes wrong, and a pipe nobody drains stops the
    # server dead once it holds 64k, halfway through a long sweep.
    with TemporaryFile("w+", encoding="utf-8", errors="replace") as spoken:
        running = subprocess.Popen(
            [command, *arguments],
            env=environment,
            cwd=str(ROOT),
            stdout=spoken,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _listening(running, spoken, port, wait)
            yield Wiki(
                url=f"http://{LOCALHOST}:{port}/mcp/",
                headers=held.header,
                key_id=held.kid,
                kept=held.label or WIKI_LABEL,
            )
        finally:
            running.terminate()
            try:
                running.wait(timeout=10)
            except subprocess.TimeoutExpired:
                running.kill()


def _spoken(spoken: IO[str]) -> str:
    """Everything the wiki has said so far, without disturbing where it writes."""
    where = spoken.tell()
    spoken.seek(0)
    try:
        return spoken.read()
    finally:
        spoken.seek(where)


def _listening(
    running: subprocess.Popen[str], spoken: IO[str], port: int, wait: float
) -> None:
    """Wait until the wiki is answering, or say what it said instead."""
    until = time.monotonic() + wait
    while time.monotonic() < until:
        if running.poll() is not None:
            said = _spoken(spoken)
            raise RuntimeError(f"the wiki stopped before it served anything:\n{said}")
        with closing(socket.socket()) as trying:
            trying.settimeout(0.5)
            if trying.connect_ex((LOCALHOST, port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(
        f"the wiki was not listening on {port} after {wait:.0f}s, having said:\n"
        f"{_spoken(spoken)}"
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
            f"no dataset at {artifact}: run `uv run poe build-test-artifact` for the "
            "hand-made one, or `uv run poe build-artifact <documents>` for a real "
            "build, and point WIKI_API_DATA_DIR at whichever you built"
        )
    if wiki_credential() is None:
        return (
            "this wiki answers holders of a key it issued, and there is none to "
            f"present. Run `uv run poe keys init` once, then `uv run poe keys issue "
            f"--label {WIKI_LABEL}`, which keeps one in "
            f"{tokens_dir(config_dir())}. Name another with "
            f"{WIKI_TOKEN_FILE_VARIABLE} in {env_of(folder)} to use that instead"
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
