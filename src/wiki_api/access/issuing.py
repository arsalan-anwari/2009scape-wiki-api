"""Make issuer keys and tokens, on an administrator's own machine.

An import contract keeps this out of anything that serves requests, so a running
service cannot mint a token even for itself. Issued tokens are copied beside the
issuer key under the signing key's mode; do not put that directory on a server.
"""

from __future__ import annotations

import json
import secrets
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

from wiki_api.access.errors import AccessMisconfigured, IssuerExists
from wiki_api.access.keys import public_key_text, withdrawn_from_file
from wiki_api.access.paths import (
    APPLICATION,
    DIRECTORY_MODE,
    PRIVATE_MODE,
    issuer_key_path,
    issuer_public_path,
    revoked_path,
    token_path,
    tokens_dir,
)
from wiki_api.access.tokens import (
    ACCESS_TOKEN_KEY,
    ISSUED_AT_KEY,
    ISSUER_KEY,
    KID_KEY,
    LABEL_KEY,
    SCHEME,
    TOKEN_TYPE_KEY,
    assemble,
    claims,
    signed_bytes,
)

if TYPE_CHECKING:
    from pathlib import Path

KEY_ID_BYTES: Final = 16


@dataclass(frozen=True)
class Issuer:
    """The key an administrator signs with, and the one their servers check with."""

    private_key: Ed25519PrivateKey
    directory: Path

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()


def create_issuer(directory: Path) -> Issuer:
    """Make the one key this administrator issues from.

    Raises `IssuerExists` rather than overwriting one, which would refuse every token
    already issued from it.
    """
    key_path = issuer_key_path(directory)
    if key_path.exists():
        raise IssuerExists(f"there is already an issuer key in {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    _restrict(directory, DIRECTORY_MODE)
    private_key = Ed25519PrivateKey.generate()
    key_path.write_bytes(
        private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    )
    _restrict(key_path, PRIVATE_MODE)
    issuer_public_path(directory).write_text(
        f"{public_key_text(private_key.public_key())}\n", encoding="utf-8"
    )
    return Issuer(private_key=private_key, directory=directory)


def load_issuer(directory: Path) -> Issuer:
    """Read the issuer key already made in this directory."""
    key_path = issuer_key_path(directory)
    try:
        raw = key_path.read_bytes()
    except OSError as error:
        raise AccessMisconfigured(f"there is no issuer key in {directory}") from error
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(raw)
    except ValueError as error:
        raise AccessMisconfigured("the issuer key is not readable") from error
    return Issuer(private_key=private_key, directory=directory)


def issue(issuer: Issuer, label: str) -> tuple[str, str]:
    """Mint one token for one client, returning it with the key id that withdraws it.

    Writes nothing down; `write_token` keeps the copy.
    """
    said = label.strip()
    if not said:
        raise AccessMisconfigured("a token needs a label saying who it is for")
    named = urlsafe_b64encode(secrets.token_bytes(KEY_ID_BYTES)).decode("ascii")
    kid = named.rstrip("=")
    payload = claims(kid, said)
    token = assemble(payload, issuer.private_key.sign(signed_bytes(payload)))
    return token, kid


def write_token(directory: Path, label: str, token: str, kid: str) -> Path:
    """Keep this token as OAuth 2.0 bearer json, where its holder can read it.

    Filed under `label`, so issuing for the same label again replaces the copy rather
    than leaving two with no way to tell which is live.
    """
    path = token_path(directory, label)
    tokens_dir(directory).mkdir(parents=True, exist_ok=True)
    _restrict(tokens_dir(directory), DIRECTORY_MODE)
    kept = {
        TOKEN_TYPE_KEY: SCHEME,
        ACCESS_TOKEN_KEY: token,
        KID_KEY: kid,
        LABEL_KEY: label.strip(),
        ISSUER_KEY: APPLICATION,
        ISSUED_AT_KEY: datetime.now(tz=UTC).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
    _restrict(path, PRIVATE_MODE)
    return path


def withdraw(directory: Path, kid: str) -> frozenset[str]:
    """Stop answering one issued key, and say which ones are now withdrawn."""
    named = kid.strip()
    if not named:
        raise AccessMisconfigured("a key has to be named to be withdrawn")
    path = revoked_path(directory)
    withdrawn = withdrawn_from_file(path) | {named}
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(withdrawn), indent=2) + "\n", encoding="utf-8")
    return withdrawn


def _restrict(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except (OSError, NotImplementedError):
        return


# test cases


def test_an_issuer_writes_a_key_a_server_can_check_with(tmp_path: Path) -> None:
    issuer = create_issuer(tmp_path / "keys")
    written = issuer_public_path(issuer.directory).read_text(encoding="utf-8")
    assert written.strip() == public_key_text(issuer.public_key)


def test_the_signing_key_never_leaves_the_administrator_side(tmp_path: Path) -> None:
    issuer = create_issuer(tmp_path / "keys")
    assert issuer_key_path(issuer.directory).exists()
    assert (
        public_key_text(issuer.public_key)
        not in issuer_key_path(issuer.directory).read_bytes().hex()
    )


def test_an_existing_issuer_is_never_stood_on(tmp_path: Path) -> None:
    import pytest

    create_issuer(tmp_path / "keys")
    with pytest.raises(IssuerExists):
        create_issuer(tmp_path / "keys")


def test_a_key_made_here_is_the_key_read_back(tmp_path: Path) -> None:
    made = create_issuer(tmp_path / "keys")
    read = load_issuer(tmp_path / "keys")
    assert read.public_key.public_bytes_raw() == made.public_key.public_bytes_raw()


def test_a_directory_with_no_issuer_says_so(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(AccessMisconfigured):
        load_issuer(tmp_path / "nothing")


def test_a_key_file_full_of_nonsense_says_so(tmp_path: Path) -> None:
    import pytest

    directory = tmp_path / "keys"
    directory.mkdir()
    issuer_key_path(directory).write_bytes(b"nonsense")
    with pytest.raises(AccessMisconfigured):
        load_issuer(directory)


def test_an_issued_token_is_answered_by_the_key_that_signed_it(tmp_path: Path) -> None:
    from wiki_api.access.tokens import Accepted, verify

    issuer = create_issuer(tmp_path / "keys")
    token, kid = issue(issuer, "the wiki")
    assert verify(token, public_key=issuer.public_key) == Accepted(
        kid=kid, label="the wiki"
    )


def test_two_tokens_are_never_the_same_token(tmp_path: Path) -> None:
    issuer = create_issuer(tmp_path / "keys")
    first, one = issue(issuer, "the wiki")
    second, other = issue(issuer, "the wiki")
    assert first != second
    assert one != other


def test_a_token_nobody_can_be_held_to_account_for_is_refused(tmp_path: Path) -> None:
    import pytest

    issuer = create_issuer(tmp_path / "keys")
    with pytest.raises(AccessMisconfigured):
        issue(issuer, "   ")


def test_no_record_of_an_issued_token_is_kept(tmp_path: Path) -> None:
    directory = tmp_path / "keys"
    issuer = create_issuer(directory)
    token, _ = issue(issuer, "the wiki")
    written = "".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in directory.iterdir()
    )
    assert token not in written


def test_withdrawing_a_key_is_remembered(tmp_path: Path) -> None:
    directory = tmp_path / "keys"
    create_issuer(directory)
    assert withdraw(directory, "one") == frozenset({"one"})
    assert withdraw(directory, "two") == frozenset({"one", "two"})
    assert withdrawn_from_file(revoked_path(directory)) == frozenset({"one", "two"})


def test_withdrawing_the_same_key_twice_changes_nothing(tmp_path: Path) -> None:
    directory = tmp_path / "keys"
    create_issuer(directory)
    withdraw(directory, "one")
    assert withdraw(directory, "one") == frozenset({"one"})


def test_a_key_that_is_not_named_cannot_be_withdrawn(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(AccessMisconfigured):
        withdraw(tmp_path / "keys", "  ")


def test_a_kept_token_is_the_token_that_was_issued(tmp_path: Path) -> None:
    from wiki_api.access.tokens import credential_from_file

    issuer = create_issuer(tmp_path / "keys")
    token, kid = issue(issuer, "Test Cases")
    path = write_token(issuer.directory, "Test Cases", token, kid)
    assert path.name == "test-cases.json"
    held = credential_from_file(path)
    assert (held.kid, held.access_token, held.label) == (kid, token, "Test Cases")


def test_a_kept_token_reads_as_json_anything_can_parse(tmp_path: Path) -> None:
    issuer = create_issuer(tmp_path / "keys")
    token, kid = issue(issuer, "demos")
    written = write_token(issuer.directory, "demos", token, kid).read_text(
        encoding="utf-8"
    )
    said = json.loads(written)
    assert said[ACCESS_TOKEN_KEY] == token
    assert said[KID_KEY] == kid
    assert said[TOKEN_TYPE_KEY] == SCHEME
    assert said[ISSUER_KEY] == APPLICATION
    assert said[ISSUED_AT_KEY].endswith("+00:00")


def test_issuing_for_the_same_label_replaces_the_copy(tmp_path: Path) -> None:
    from wiki_api.access.tokens import credential_from_file

    issuer = create_issuer(tmp_path / "keys")
    first, one = issue(issuer, "demos")
    write_token(issuer.directory, "demos", first, one)
    second, other = issue(issuer, "demos")
    path = write_token(issuer.directory, "demos", second, other)
    assert credential_from_file(path).access_token == second
    assert credential_from_file(path).kid == other
    assert len(list(tokens_dir(issuer.directory).iterdir())) == 1


def test_a_kept_token_is_no_more_readable_than_the_key_that_signed_it(
    tmp_path: Path,
) -> None:
    import stat

    issuer = create_issuer(tmp_path / "keys")
    token, kid = issue(issuer, "demos")
    path = write_token(issuer.directory, "demos", token, kid)
    assert stat.S_IMODE(path.stat().st_mode) == PRIVATE_MODE


def test_a_token_file_that_says_nothing_useful_says_so(tmp_path: Path) -> None:
    import pytest

    from wiki_api.access.tokens import credential_from_file

    path = tmp_path / "half.json"
    path.write_text('{"kid": "abcd"}', encoding="utf-8")
    with pytest.raises(AccessMisconfigured):
        credential_from_file(path)


def test_a_token_file_that_is_not_there_says_so(tmp_path: Path) -> None:
    import pytest

    from wiki_api.access.tokens import credential_from_file

    with pytest.raises(AccessMisconfigured):
        credential_from_file(tmp_path / "absent.json")
