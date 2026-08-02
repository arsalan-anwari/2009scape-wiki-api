"""The administrator's side of access: make an issuer key, issue a token for a client,
stop answering one, and print what a server needs to be told.

This runs on a person's own machine. Nothing that serves requests imports it.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Final

from wiki_api.access.bans import FileBans
from wiki_api.access.errors import AccessError
from wiki_api.access.issuing import (
    create_issuer,
    issue,
    load_issuer,
    withdraw,
    write_token,
)
from wiki_api.access.keys import public_key_text, withdrawn_from_file
from wiki_api.access.paths import (
    banned_path,
    config_dir,
    issuer_public_path,
    revoked_path,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

PUBLIC_KEY_VARIABLE: Final = "WIKI_API_AUTH_PUBLIC_KEY"
KEEP_IT_SAFE: Final = (
    "Treat this like a password. The copy kept beside your issuer key is readable by "
    "you alone; issuing for the same label again replaces it."
)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one key management command."""
    parsed = _parser().parse_args(argv)
    directory: Path = parsed.directory if parsed.directory else config_dir()
    try:
        return _ran(parsed, directory)
    except AccessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _ran(parsed: argparse.Namespace, directory: Path) -> int:
    if parsed.command == "init":
        return _initialised(directory)
    if parsed.command == "issue":
        return _issued(directory, parsed.label)
    if parsed.command == "revoke":
        return _withdrew(directory, parsed.kid)
    if parsed.command == "banned":
        return _banned(directory)
    if parsed.command == "unban":
        return _unbanned(directory, parsed.caller)
    return _shown(directory)


def _initialised(directory: Path) -> int:
    issuer = create_issuer(directory)
    print(f"issuer key written to {directory}")
    print(f"{PUBLIC_KEY_VARIABLE}={public_key_text(issuer.public_key)}")
    return 0


def _issued(directory: Path, label: str) -> int:
    token, kid = issue(load_issuer(directory), label)
    path = write_token(directory, label, token, kid)
    print(f"key id: {kid}")
    print(f"token:  {token}")
    print(f"kept in {path}")
    print(KEEP_IT_SAFE)
    return 0


def _withdrew(directory: Path, kid: str) -> int:
    withdrawn = withdraw(directory, kid)
    print(f"{kid} is no longer answered")
    print(f"{len(withdrawn)} withdrawn in total, listed in {revoked_path(directory)}")
    return 0


def _shown(directory: Path) -> int:
    issuer = load_issuer(directory)
    print(f"directory:  {directory}")
    print(f"public key: {public_key_text(issuer.public_key)}")
    print(f"written at: {issuer_public_path(directory)}")
    withdrawn = sorted(withdrawn_from_file(revoked_path(directory)))
    print(f"withdrawn:  {', '.join(withdrawn) if withdrawn else 'none'}")
    return 0


def _banned(directory: Path) -> int:
    listed = FileBans(banned_path(directory)).listed()
    if not listed:
        print("nobody is shut out")
        return 0
    for ban in listed:
        print(f"{ban.caller}\tuntil {ban.at.isoformat()}\tshut out {ban.strikes}x")
    return 0


def _unbanned(directory: Path, caller: str) -> int:
    if FileBans(banned_path(directory)).lift(caller):
        print(f"{caller} is answered again")
        return 0
    print(f"{caller} was not being refused")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keys",
        description=(
            "Issue and withdraw the keys this service answers, and read who it is "
            "refusing."
        ),
    )
    parser.add_argument(
        "--directory",
        type=_path,
        default=None,
        help="where to keep the keys; defaults to this platform's config directory",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="make the key this administrator issues from")
    issuing = commands.add_parser("issue", help="issue one token for one client")
    issuing.add_argument("--label", required=True, help="who the token is for")
    withdrawing = commands.add_parser("revoke", help="stop answering one issued key")
    withdrawing.add_argument("--kid", required=True, help="the key id to withdraw")
    commands.add_parser("show", help="print what a server has to be told")
    commands.add_parser("banned", help="list the addresses not being answered")
    lifting = commands.add_parser("unban", help="answer one address again")
    lifting.add_argument("--caller", required=True, help="the address to answer again")
    return parser


def _path(given: str) -> Path:
    from pathlib import Path as Location

    return Location(given)


if __name__ == "__main__":
    raise SystemExit(main())


# test cases


def test_making_a_key_prints_what_a_server_has_to_be_told(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    assert main(["--directory", str(tmp_path / "keys"), "init"]) == 0
    printed = capsys.readouterr().out
    assert PUBLIC_KEY_VARIABLE in printed


def test_making_a_key_twice_fails_rather_than_replacing_one(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    where = str(tmp_path / "keys")
    main(["--directory", where, "init"])
    assert main(["--directory", where, "init"]) == 1
    assert "error:" in capsys.readouterr().err


def test_a_token_is_printed_and_said_to_be_a_secret(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    where = str(tmp_path / "keys")
    main(["--directory", where, "init"])
    capsys.readouterr()
    assert main(["--directory", where, "issue", "--label", "the wiki"]) == 0
    printed = capsys.readouterr().out
    assert "wk1." in printed
    assert KEEP_IT_SAFE in printed


def test_issuing_keeps_a_copy_under_a_name_taken_from_the_label(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    from wiki_api.access.paths import token_path
    from wiki_api.access.tokens import credential_from_file

    assert isinstance(capsys, pytest.CaptureFixture)
    directory = tmp_path / "keys"
    main(["--directory", str(directory), "init"])
    capsys.readouterr()
    assert main(["--directory", str(directory), "issue", "--label", "Test Cases"]) == 0
    kept = token_path(directory, "Test Cases")
    assert kept.name == "test-cases.json"
    assert str(kept) in capsys.readouterr().out
    held = credential_from_file(kept)
    assert held.access_token.startswith("wk1.")
    assert held.kid
    assert held.header == {"Authorization": f"Bearer {held.access_token}"}


def test_a_label_that_cannot_be_a_file_name_is_refused(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    directory = tmp_path / "keys"
    main(["--directory", str(directory), "init"])
    capsys.readouterr()
    given = ["--directory", str(directory), "issue", "--label", "../elsewhere"]
    assert main(given) == 1
    assert "error:" in capsys.readouterr().err


def test_issuing_from_a_directory_with_no_key_fails_plainly(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    given = ["--directory", str(tmp_path / "nothing"), "issue", "--label", "x"]
    assert main(given) == 1
    assert "error:" in capsys.readouterr().err


def test_a_withdrawn_key_is_reported_as_withdrawn(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    where = str(tmp_path / "keys")
    main(["--directory", where, "init"])
    capsys.readouterr()
    assert main(["--directory", where, "revoke", "--kid", "abcd"]) == 0
    assert "abcd" in capsys.readouterr().out


def test_what_a_server_needs_can_be_asked_for_again(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    where = str(tmp_path / "keys")
    main(["--directory", where, "init"])
    capsys.readouterr()
    assert main(["--directory", where, "show"]) == 0
    printed = capsys.readouterr().out
    assert "public key:" in printed
    assert "withdrawn:  none" in printed


def test_nobody_is_shut_out_to_begin_with(tmp_path: Path, capsys: object) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    assert main(["--directory", str(tmp_path / "keys"), "banned"]) == 0
    assert "nobody is shut out" in capsys.readouterr().out


def test_who_is_shut_out_can_be_read(tmp_path: Path, capsys: object) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    directory = tmp_path / "keys"
    FileBans(banned_path(directory)).shut_out("1.2.3.4", 900.0)
    assert main(["--directory", str(directory), "banned"]) == 0
    printed = capsys.readouterr().out
    assert "1.2.3.4" in printed
    assert "until" in printed


def test_an_address_can_be_answered_again_by_hand(
    tmp_path: Path, capsys: object
) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    directory = tmp_path / "keys"
    bans = FileBans(banned_path(directory))
    bans.shut_out("1.2.3.4", 900.0)
    assert main(["--directory", str(directory), "unban", "--caller", "1.2.3.4"]) == 0
    assert "answered again" in capsys.readouterr().out
    assert FileBans(banned_path(directory)).left("1.2.3.4") is None


def test_lifting_a_ban_nobody_has_says_so(tmp_path: Path, capsys: object) -> None:
    import pytest

    assert isinstance(capsys, pytest.CaptureFixture)
    given = ["--directory", str(tmp_path / "keys"), "unban", "--caller", "1.2.3.4"]
    assert main(given) == 0
    assert "was not being refused" in capsys.readouterr().out


def test_a_command_nobody_offers_is_refused() -> None:
    import pytest

    with pytest.raises(SystemExit):
        main(["nonsense"])
