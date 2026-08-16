"""One entry point behind every way of installing this."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

from wiki_api.domain.errors import KnowledgeError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from wiki_api.config import Settings

COMMANDS: Final = ("serve", "mcp", "keys", "data")

USAGE: Final = f"""usage: scape2009-wiki-api <{"|".join(COMMANDS)}> [arguments]

  serve   the http contract, the tools, or both, as the settings ask
  mcp     the tools alone, over stdio or http
  keys    make an issuer key, issue a token, withdraw one
  data    fetch the published dataset, or say where one is looked for

Every setting is a WIKI_API_ environment variable or a line of deploy.json.
"""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the named command with the remaining arguments, or explain the names."""
    said = list(sys.argv[1:] if argv is None else argv)
    named = said[0] if said else ""
    if named not in COMMANDS:
        stream = sys.stderr if named else sys.stdout
        print(USAGE, file=stream)
        return 2 if named else 0
    return _ran(named, said[1:])


def _ran(command: str, rest: Sequence[str]) -> int:
    """Import only the command being run, so starting the tools costs no more than it
    has to.
    """
    if command == "keys":
        return keys(rest)
    if command == "data":
        return data(rest)
    if command == "mcp":
        return tools(rest)
    return serve(rest)


def keys(argv: Sequence[str] | None = None) -> int:
    """Make an issuer key, issue a token for a client, or stop answering one."""
    from wiki_api.access.cli import main as issuing

    return issuing(argv)


def data(argv: Sequence[str] | None = None) -> int:
    """Fetch the published dataset, or say where one is looked for."""
    from wiki_api.dataset import main as fetching

    return _reported(lambda: fetching(argv))


def tools(argv: Sequence[str] | None = None) -> int:
    """Serve the tools alone, over whichever transport the settings ask for."""
    _refuse_arguments("mcp", argv)

    def started() -> int:
        from wiki_api.config import Settings
        from wiki_api.surfaces.mcp.server import serve_tools

        serve_tools(Settings(surfaces="mcp"))
        return 0

    return _reported(started)


def serve(argv: Sequence[str] | None = None) -> int:
    """Serve whichever surfaces this deployment is configured to serve."""
    _refuse_arguments("serve", argv)

    def started() -> int:
        from wiki_api.config import get_settings
        from wiki_api.serve import main as serving

        _refuse_without_a_dataset(get_settings())
        serving()
        return 0

    return _reported(started)


def _refuse_without_a_dataset(settings: Settings) -> None:
    """Say there is no dataset before a server is started rather than during it."""
    from wiki_api.repository.errors import ArtifactUnavailable

    if not settings.artifact_path.is_file():
        raise ArtifactUnavailable(settings.artifact_path)


def _refuse_arguments(command: str, argv: Sequence[str] | None) -> None:
    """Say so rather than ignoring arguments a command does not read."""
    said = list(sys.argv[1:] if argv is None else argv)
    if said:
        print(
            f"{command} takes no arguments: every setting is a WIKI_API_ environment "
            "variable or a line of deploy.json",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _reported(started: Callable[[], int]) -> int:
    """Run a command, turning what it cannot do into a line rather than a traceback."""
    try:
        return started()
    except ValidationError as misconfigured:
        for line in _lines(misconfigured):
            print(f"error: {line}", file=sys.stderr)
        return 2
    except KnowledgeError as missing:
        from wiki_api.dataset import invoked_as

        print(f"error: {missing}", file=sys.stderr)
        print(
            f"fetch a dataset with `{invoked_as()} pull`, or point "
            "WIKI_API_DATA_DIR at one you already have",
            file=sys.stderr,
        )
        return 2
    except OSError as refused:
        print(f"error: {refused.strerror or refused}", file=sys.stderr)
        if refused.filename:
            print(f"  while reading {refused.filename}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover ,a person stopping a server
        return 130


def _lines(misconfigured: ValidationError) -> list[str]:
    """Say what is wrong with the settings in the words the setting was written in."""
    said = []
    for problem in misconfigured.errors():
        where = ".".join(str(part) for part in problem["loc"])
        message = str(problem["msg"]).removeprefix("Value error, ")
        said.append(f"{where}: {message}" if where else message)
    return said or [str(misconfigured)]


if __name__ == "__main__":  # pragma: no cover, the frozen build calls main directly
    sys.exit(main())


# test cases


def test_a_name_nobody_serves_is_explained_rather_than_run(capsys: object) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    assert main(["telepathy"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_asking_for_nothing_says_what_there_is(capsys: object) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    assert main([]) == 0
    said = capsys.readouterr().out
    assert all(command in said for command in COMMANDS)


def test_every_way_of_installing_this_offers_the_same_commands() -> None:
    """The console scripts, the container and the frozen build all name these."""
    assert COMMANDS == ("serve", "mcp", "keys", "data")


def test_settings_that_cannot_start_say_so_in_one_line(
    monkeypatch: object, capsys: object, tmp_path: object
) -> None:
    from pathlib import Path

    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    assert isinstance(tmp_path, Path)
    monkeypatch.setenv("WIKI_API_CONFIG_DIR", str(tmp_path / "nothing"))
    monkeypatch.delenv("WIKI_API_AUTH_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("WIKI_API_SURFACES", raising=False)
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "required")
    assert serve() == 2
    said = capsys.readouterr().err
    assert said.count("error:") == 1
    assert "Traceback" not in said
    assert "scape2009-wiki-keys init" in said


def test_a_missing_dataset_says_how_to_get_one(
    monkeypatch: object, capsys: object, tmp_path: object
) -> None:
    from pathlib import Path

    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    assert isinstance(tmp_path, Path)
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "off")
    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", "stdio")
    assert tools() == 2
    said = capsys.readouterr().err
    assert "no knowledge artifact" in said
    assert "scape2009-wiki-data pull" in said
    assert "Traceback" not in said


def test_the_contract_says_there_is_no_dataset_before_a_server_is_started(
    monkeypatch: object, capsys: object, tmp_path: object
) -> None:
    """Opened inside the lifespan, a missing artifact reaches the caller as a uvicorn
    traceback and an `Application startup failed`, which names nothing to do.
    """
    from pathlib import Path

    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    assert isinstance(tmp_path, Path)
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("WIKI_API_AUTH_MODE", "off")
    monkeypatch.delenv("WIKI_API_SURFACES", raising=False)
    assert serve() == 2
    said = capsys.readouterr().err
    assert "no knowledge artifact" in said
    assert "pull" in said


def test_a_setting_passed_as_an_argument_is_refused_rather_than_dropped(
    capsys: object,
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    with pytest.raises(SystemExit) as stopped:
        serve(["--port", "9000"])
    assert stopped.value.code == 2
    assert "deploy.json" in capsys.readouterr().err


def test_a_dataset_that_cannot_be_read_says_which_file(
    monkeypatch: object, capsys: object, tmp_path: object
) -> None:
    """A volume mounted with the wrong owner is the commonest way this happens."""
    from pathlib import Path

    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    assert isinstance(tmp_path, Path)
    artifact = tmp_path / "knowledge.sqlite3"

    def refuse() -> int:
        raise PermissionError(13, "Permission denied", str(artifact))

    assert _reported(refuse) == 2
    said = capsys.readouterr().err
    assert "Permission denied" in said
    assert str(artifact) in said
    assert "Traceback" not in said


def test_a_console_script_reads_the_arguments_nobody_handed_it(
    monkeypatch: object, capsys: object
) -> None:
    """An entry point calls `serve()` with nothing, so the flags are still on argv."""
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    monkeypatch.setattr(sys, "argv", ["scape2009-wiki-serve", "--port", "9000"])
    with pytest.raises(SystemExit) as stopped:
        serve()
    assert stopped.value.code == 2
    assert "deploy.json" in capsys.readouterr().err


def test_a_command_handed_no_arguments_on_purpose_still_runs(
    monkeypatch: object,
) -> None:
    """The dispatcher passes an empty list, which is not the same as passing nothing."""
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    monkeypatch.setattr(sys, "argv", ["scape2009-wiki-api", "serve"])
    _refuse_arguments("serve", [])
