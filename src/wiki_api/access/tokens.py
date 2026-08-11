"""Accept or refuse the token a client presents.

A token has no expiry, so `withdrawn` is the only way one stops being answered.
"""

from __future__ import annotations

import json
from base64 import b64decode, urlsafe_b64encode
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wiki_api.access.errors import AccessMisconfigured

if TYPE_CHECKING:
    from pathlib import Path

PREFIX: Final = "wk1"
VERSION: Final = 1
SIGNING_CONTEXT: Final = b"scape2009-wiki-api/token/v1\x00"
SCHEME: Final = "Bearer"
PART_COUNT: Final = 3
MOST_TOKEN_CHARS: Final = 4096

ACCESS_TOKEN_KEY: Final = "access_token"
TOKEN_TYPE_KEY: Final = "token_type"
KID_KEY: Final = "kid"
LABEL_KEY: Final = "label"
ISSUER_KEY: Final = "issuer"
ISSUED_AT_KEY: Final = "issued_at"


class Reason(StrEnum):
    """Why a token was refused, for counting rather than for telling."""

    MALFORMED = "malformed"
    BAD_SIGNATURE = "bad_signature"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class Accepted:
    """The token was issued by this issuer and has not been withdrawn."""

    kid: str
    label: str


@dataclass(frozen=True)
class Refused:
    """The token is not one this service answers."""

    reason: Reason


Verdict = Accepted | Refused


def claims(kid: str, label: str) -> bytes:
    """Write the claims for `kid` and `label`, byte-for-byte the one way they are ever
    written.
    """
    return json.dumps(
        {"v": VERSION, "kid": kid, "label": label},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8")


def signed_bytes(payload: bytes) -> bytes:
    """Put the signing marker in front of `payload`, giving the bytes a signature
    covers.

    The marker is what stops a signature made here being read as one made elsewhere.
    """
    return SIGNING_CONTEXT + payload


def assemble(payload: bytes, signature: bytes) -> str:
    """Join the claims and their signature into the one word a client carries."""
    return f"{PREFIX}.{_written(payload)}.{_written(signature)}"


def verify(
    token: str, *, public_key: Ed25519PublicKey, withdrawn: frozenset[str] = frozenset()
) -> Verdict:
    """Decide whether this token is one this service answers."""
    if len(token) > MOST_TOKEN_CHARS:
        return Refused(reason=Reason.MALFORMED)
    parts = token.split(".")
    if len(parts) != PART_COUNT or parts[0] != PREFIX:
        return Refused(reason=Reason.MALFORMED)
    payload = _read(parts[1])
    signature = _read(parts[2])
    if payload is None or signature is None:
        return Refused(reason=Reason.MALFORMED)
    try:
        public_key.verify(signature, signed_bytes(payload))
    except InvalidSignature:
        return Refused(reason=Reason.BAD_SIGNATURE)
    return _claimed(payload, withdrawn)


def presented(header: str | None) -> str | None:
    """Pull the token out of an `Authorization` header, or return nothing."""
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != SCHEME.lower() or not token.strip():
        return None
    return token.strip()


@dataclass(frozen=True)
class Credential:
    """One issued token as it is kept on disk, and how to present it."""

    access_token: str
    token_type: str
    kid: str
    label: str

    @property
    def header(self) -> dict[str, str]:
        """Build the one header a holder puts on a request."""
        return {"Authorization": f"{self.token_type} {self.access_token}"}


def credential_from_text(written: str, *, where: str = "this token") -> Credential:
    """Read a kept token, as the bearer json `poe keys issue` writes or as a bare token.

    `where` names the source in the error.
    """
    said = written.strip()
    if said.startswith(f"{PREFIX}."):
        return _from_bare(said)
    found = _as_json(said)
    access = found.get(ACCESS_TOKEN_KEY, "")
    kid = found.get(KID_KEY, "")
    if not access or not kid:
        raise AccessMisconfigured(
            f"{where} does not carry both {KID_KEY} and {ACCESS_TOKEN_KEY}"
        )
    return Credential(
        access_token=access,
        token_type=found.get(TOKEN_TYPE_KEY) or SCHEME,
        kid=kid,
        label=found.get(LABEL_KEY, ""),
    )


def credential_from_file(path: Path) -> Credential:
    """Read the token kept at this path."""
    try:
        written = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AccessMisconfigured(f"there is no token kept at {path}") from error
    return credential_from_text(written, where=str(path))


def _from_bare(token: str) -> Credential:
    """Wrap a bare token, reading its key id out of its own unchecked claims.

    Use that key id to say which key a run presents, never to trust it; `verify` is
    what decides.
    """
    return Credential(
        access_token=token, token_type=SCHEME, kid=_claimed_kid(token), label=""
    )


def _claimed_kid(token: str) -> str:
    parts = token.split(".")
    if len(parts) != PART_COUNT:
        return ""
    payload = _read(parts[1])
    if payload is None:
        return ""
    try:
        said = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    kid = said.get("kid") if isinstance(said, dict) else None
    return kid if isinstance(kid, str) else ""


def _as_json(written: str) -> dict[str, str]:
    try:
        said = json.loads(written)
    except json.JSONDecodeError as error:
        raise AccessMisconfigured("a kept token has to be readable json") from error
    if not isinstance(said, dict):
        raise AccessMisconfigured("a kept token has to be one json object")
    return {key: value for key, value in said.items() if isinstance(value, str)}


def _claimed(payload: bytes, withdrawn: frozenset[str]) -> Verdict:
    try:
        said = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return Refused(reason=Reason.MALFORMED)
    if not isinstance(said, dict) or said.get("v") != VERSION:
        return Refused(reason=Reason.MALFORMED)
    kid = said.get("kid")
    label = said.get("label")
    if not isinstance(kid, str) or not isinstance(label, str) or not kid:
        return Refused(reason=Reason.MALFORMED)
    if kid in withdrawn:
        return Refused(reason=Reason.WITHDRAWN)
    return Accepted(kid=kid, label=label)


def _written(raw: bytes) -> str:
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _read(written: str) -> bytes | None:
    padded = written + "=" * (-len(written) % 4)
    try:
        return b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError):
        return None


# test cases


def _issuer() -> tuple[object, Ed25519PublicKey]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return private_key, private_key.public_key()


def _token(kid: str = "abcd", label: str = "wiki") -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key, _ = _issuer()
    assert isinstance(private_key, Ed25519PrivateKey)
    payload = claims(kid, label)
    return assemble(payload, private_key.sign(signed_bytes(payload)))


def test_a_token_this_issuer_signed_is_answered() -> None:
    _, public_key = _issuer()
    verdict = verify(_token(), public_key=public_key)
    assert verdict == Accepted(kid="abcd", label="wiki")


def test_the_same_claims_always_produce_the_same_token() -> None:
    assert _token() == _token()


def test_a_token_carries_no_moment_it_stops_working() -> None:
    assert b"exp" not in claims("abcd", "wiki")
    assert b"iat" not in claims("abcd", "wiki")


def test_a_token_says_which_version_of_this_format_it_is() -> None:
    assert _token().startswith(f"{PREFIX}.")


def test_a_tampered_claim_is_refused() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key, public_key = _issuer()
    assert isinstance(private_key, Ed25519PrivateKey)
    payload = claims("abcd", "wiki")
    signature = private_key.sign(signed_bytes(payload))
    forged = assemble(claims("abcd", "somebody else"), signature)
    assert verify(forged, public_key=public_key) == Refused(reason=Reason.BAD_SIGNATURE)


def test_a_token_from_another_issuer_is_refused() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    stranger = Ed25519PrivateKey.from_private_bytes(bytes(range(32, 64)))
    payload = claims("abcd", "wiki")
    theirs = assemble(payload, stranger.sign(signed_bytes(payload)))
    _, public_key = _issuer()
    assert verify(theirs, public_key=public_key) == Refused(reason=Reason.BAD_SIGNATURE)


def test_a_signature_made_for_something_else_is_refused() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key, public_key = _issuer()
    assert isinstance(private_key, Ed25519PrivateKey)
    payload = claims("abcd", "wiki")
    unmarked = assemble(payload, private_key.sign(payload))
    assert verify(unmarked, public_key=public_key) == Refused(
        reason=Reason.BAD_SIGNATURE
    )


def test_a_withdrawn_key_is_refused_however_well_it_is_signed() -> None:
    _, public_key = _issuer()
    verdict = verify(_token(), public_key=public_key, withdrawn=frozenset({"abcd"}))
    assert verdict == Refused(reason=Reason.WITHDRAWN)


def test_anything_that_is_not_a_token_is_refused() -> None:
    _, public_key = _issuer()
    for junk in ("", "nonsense", "wk1.only-two", "wk2.a.b", "wk1.@@@.@@@", "a.b.c.d"):
        assert verify(junk, public_key=public_key) == Refused(reason=Reason.MALFORMED)


def test_a_token_nobody_could_hold_is_refused_before_it_is_read() -> None:
    _, public_key = _issuer()
    huge = f"{PREFIX}.{'a' * MOST_TOKEN_CHARS}.{'a' * MOST_TOKEN_CHARS}"
    assert verify(huge, public_key=public_key) == Refused(reason=Reason.MALFORMED)


def test_claims_this_format_does_not_know_are_refused() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key, public_key = _issuer()
    assert isinstance(private_key, Ed25519PrivateKey)
    for said in (b'{"v":2,"kid":"a","label":"b"}', b"[]", b"{}", b"not json"):
        token = assemble(said, private_key.sign(signed_bytes(said)))
        assert verify(token, public_key=public_key) == Refused(reason=Reason.MALFORMED)


def test_a_request_that_carried_a_token_hands_it_over() -> None:
    assert presented("Bearer wk1.a.b") == "wk1.a.b"
    assert presented("bearer wk1.a.b") == "wk1.a.b"


def test_a_request_that_carried_nothing_usable_hands_over_nothing() -> None:
    for header in (None, "", "wk1.a.b", "Basic abcdef", "Bearer", "Bearer  "):
        assert presented(header) is None


def test_a_token_kept_as_json_is_read_back_whole() -> None:
    written = json.dumps(
        {
            TOKEN_TYPE_KEY: "Bearer",
            ACCESS_TOKEN_KEY: "wk1.aaa.bbb",
            KID_KEY: "abcd",
            LABEL_KEY: "demos",
        }
    )
    held = credential_from_text(written)
    assert held.access_token == "wk1.aaa.bbb"
    assert held.kid == "abcd"
    assert held.label == "demos"
    assert held.header == {"Authorization": "Bearer wk1.aaa.bbb"}


def test_the_two_line_form_this_used_to_be_is_refused() -> None:
    import pytest

    with pytest.raises(AccessMisconfigured):
        credential_from_text("KEY_ID=abcd\nTOKEN=wk1.aaa.bbb\n")


def test_a_bare_token_says_which_key_it_is_without_being_believed() -> None:
    written = _token(kid="abcd", label="wiki")
    held = credential_from_text(written)
    assert held.access_token == written
    assert held.kid == "abcd"
    assert held.label == ""


def test_something_that_is_not_a_credential_at_all_says_so() -> None:
    import pytest

    for written in ("", "{}", "nonsense", '{"kid": "abcd"}'):
        with pytest.raises(AccessMisconfigured):
            credential_from_text(written)
