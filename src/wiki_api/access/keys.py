"""Read what a running service is given: an issuer's public key and the withdrawn key
list.

Nothing here can produce a key, so a process calling only this module cannot mint a
token.
"""

from __future__ import annotations

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from wiki_api.access.errors import AccessMisconfigured

if TYPE_CHECKING:
    from pathlib import Path

KEY_BYTES = 32


def public_key_text(public_key: Ed25519PublicKey) -> str:
    """Write an issuer's public key so it fits in an environment variable."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def public_key_from_text(written: str) -> Ed25519PublicKey:
    """Read a public key back from that written form."""
    text = written.strip()
    if not text:
        raise AccessMisconfigured("the issuer public key is empty")
    padded = text + "=" * (-len(text) % 4)
    try:
        raw = urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise AccessMisconfigured("the issuer public key is not readable") from error
    if len(raw) != KEY_BYTES:
        raise AccessMisconfigured("the issuer public key is the wrong length")
    return Ed25519PublicKey.from_public_bytes(raw)


def public_key_from_file(path: Path) -> Ed25519PublicKey:
    """Read a public key from a file rather than from the environment."""
    try:
        written = path.read_text(encoding="utf-8")
    except OSError as error:
        raise AccessMisconfigured("the issuer public key cannot be read") from error
    return public_key_from_text(written)


def withdrawn_from_file(path: Path) -> frozenset[str]:
    """Read which issued keys are no longer answered.

    A missing file means none are; an unreadable one raises, because carrying on would
    answer keys somebody meant to stop.
    """
    if not path.exists():
        return frozenset()
    try:
        listed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AccessMisconfigured("the withdrawn key list is not readable") from error
    if not isinstance(listed, list) or not all(isinstance(kid, str) for kid in listed):
        raise AccessMisconfigured("the withdrawn key list is not a list of keys")
    return frozenset(listed)


# test cases


def _public_key() -> Ed25519PublicKey:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(bytes(range(32))).public_key()


def test_a_key_survives_being_written_down_and_read_back() -> None:
    written = public_key_text(_public_key())
    assert public_key_from_text(written).public_bytes_raw() == (
        _public_key().public_bytes_raw()
    )


def test_a_written_key_fits_in_an_environment_variable() -> None:
    written = public_key_text(_public_key())
    assert "=" not in written
    assert "\n" not in written


def test_surrounding_whitespace_in_a_key_file_is_forgiven() -> None:
    written = f"  {public_key_text(_public_key())}\n"
    assert public_key_from_text(written).public_bytes_raw()


def test_something_that_is_not_a_key_is_refused_loudly() -> None:
    import pytest

    for junk in ("", "   ", "@@@@", "c2hvcnQ="):
        with pytest.raises(AccessMisconfigured):
            public_key_from_text(junk)


def test_a_key_file_that_is_not_there_is_a_misconfiguration(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(AccessMisconfigured):
        public_key_from_file(tmp_path / "absent.pub")


def test_a_key_file_is_read_the_same_as_a_variable(tmp_path: Path) -> None:
    path = tmp_path / "issuer.pub"
    path.write_text(public_key_text(_public_key()), encoding="utf-8")
    assert public_key_from_file(path).public_bytes_raw() == (
        _public_key().public_bytes_raw()
    )


def test_no_list_of_withdrawn_keys_means_none_were_withdrawn(tmp_path: Path) -> None:
    assert withdrawn_from_file(tmp_path / "absent.json") == frozenset()


def test_the_withdrawn_keys_are_read_as_written(tmp_path: Path) -> None:
    path = tmp_path / "revoked.json"
    path.write_text('["one", "two"]', encoding="utf-8")
    assert withdrawn_from_file(path) == frozenset({"one", "two"})


def test_an_unreadable_list_of_withdrawn_keys_is_never_ignored(
    tmp_path: Path,
) -> None:
    import pytest

    for written in ("{}", "[1, 2]", "not json"):
        path = tmp_path / "revoked.json"
        path.write_text(written, encoding="utf-8")
        with pytest.raises(AccessMisconfigured):
            withdrawn_from_file(path)
