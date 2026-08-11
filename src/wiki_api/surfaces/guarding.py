"""Decide who gets answered, once for both surfaces.

Every refusal reads the same to the caller; the `Outcome` saying which it was is for
counting, not for telling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from wiki_api.access import (
    Accepted,
    Guard,
    InProcessGuard,
    ShutOut,
    Throttled,
    presented,
    public_key_from_file,
    public_key_from_text,
    verify,
    withdrawn_from_file,
)
from wiki_api.access.bans import FileBans
from wiki_api.access.errors import AccessMisconfigured
from wiki_api.access.paths import banned_path, config_dir

if TYPE_CHECKING:
    from pathlib import Path

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    from wiki_api.config import Settings

ANONYMOUS_PATHS: Final = frozenset({"/health"})
FORWARDED_HEADER: Final = "x-forwarded-for"
UNKNOWN_CALLER: Final = "unknown"
ANYWHERE: Final = "*"


class Outcome(StrEnum):
    """What is to be done with a request."""

    ALLOWED = "allowed"
    UNAUTHENTICATED = "unauthenticated"
    BLOCKED = "blocked"
    THROTTLED = "throttled"


@dataclass(frozen=True)
class Decision:
    """Whether to answer, and how long to say to wait when not."""

    outcome: Outcome
    after: int | None = None

    @property
    def allowed(self) -> bool:
        return self.outcome is Outcome.ALLOWED


@dataclass(frozen=True)
class Access:
    """Everything it takes to decide whether one request is answered."""

    public_key: Ed25519PublicKey
    withdrawn: frozenset[str]
    guard: Guard
    trusted: frozenset[str]

    def decide(self, token: str | None, caller: str) -> Decision:
        """Decide whether to answer this token from this address."""
        shut_out = self.guard.shut_out(caller)
        if isinstance(shut_out, ShutOut):
            return Decision(outcome=Outcome.BLOCKED, after=shut_out.after)
        if token is None:
            self.guard.refused(caller)
            return Decision(outcome=Outcome.UNAUTHENTICATED)
        verdict = verify(token, public_key=self.public_key, withdrawn=self.withdrawn)
        if not isinstance(verdict, Accepted):
            self.guard.refused(caller)
            return Decision(outcome=Outcome.UNAUTHENTICATED)
        share = self.guard.admits(verdict.kid)
        if isinstance(share, Throttled):
            return Decision(outcome=Outcome.THROTTLED, after=share.after)
        return Decision(outcome=Outcome.ALLOWED)

    def holds(self, token: str) -> Accepted | None:
        """Return who this token was issued to, or nothing when it is not ours."""
        verdict = verify(token, public_key=self.public_key, withdrawn=self.withdrawn)
        return verdict if isinstance(verdict, Accepted) else None


def access_from(settings: Settings) -> Access | None:
    """Assemble what it takes to guard requests, or nothing when `auth_mode` is off."""
    if settings.auth_mode == "off":
        return None
    return Access(
        public_key=_public_key(settings),
        withdrawn=_withdrawn(settings),
        guard=InProcessGuard(
            rate=settings.rate_per_second,
            burst=settings.rate_burst,
            most_refusals=settings.max_refusals,
            window=settings.refusal_window,
            ban=settings.ban_seconds,
            tracked=settings.guard_entries,
            bans=FileBans(_ban_file(settings), most=settings.guard_entries),
        ),
        trusted=frozenset(settings.trusted_proxies),
    )


def caller_of(peer: str | None, forwarded: str | None, trusted: frozenset[str]) -> str:
    """Pick the address to hold responsible: the socket's, unless the peer is in
    `trusted`.

    A forwarded address from anywhere else would let one caller dodge a shut-out and
    get another shut out instead.
    """
    address = peer or UNKNOWN_CALLER
    if address not in trusted or not forwarded:
        return address
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    return hops[-1] if hops else address


def token_of(header: str | None) -> str | None:
    """Pull the token out of an `Authorization` header."""
    return presented(header)


def anonymous(path: str) -> bool:
    """Say whether this path is answered without a token."""
    return path in ANONYMOUS_PATHS


def _public_key(settings: Settings) -> Ed25519PublicKey:
    """Load the key tokens are checked against: the configured one, else what
    `poe keys init` left beside its files.
    """
    if settings.auth_public_key:
        return public_key_from_text(settings.auth_public_key)
    if settings.auth_public_key_file is not None:
        return public_key_from_file(settings.auth_public_key_file)
    found = settings.issuer_public_file
    if found is not None:
        return public_key_from_file(found)
    raise AccessMisconfigured(
        "this deployment answers only holders of a key, but was given no key to "
        "check them against"
    )


def _ban_file(settings: Settings) -> Path:
    """Locate the ban file: `ban_file` when set, else beside the config directory."""
    if settings.ban_file is not None:
        return settings.ban_file
    return banned_path(config_dir())


def _withdrawn(settings: Settings) -> frozenset[str]:
    if settings.auth_revoked_file is None:
        return frozenset()
    return withdrawn_from_file(settings.auth_revoked_file)


# test cases


def _keys() -> tuple[object, Ed25519PublicKey]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    return private_key, private_key.public_key()


def _token(kid: str = "abcd", label: str = "wiki") -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from wiki_api.access.tokens import assemble, claims, signed_bytes

    private_key, _ = _keys()
    assert isinstance(private_key, Ed25519PrivateKey)
    payload = claims(kid, label)
    return assemble(payload, private_key.sign(signed_bytes(payload)))


def _access(
    guard: Guard | None = None, withdrawn: frozenset[str] = frozenset()
) -> Access:
    _, public_key = _keys()
    return Access(
        public_key=public_key,
        withdrawn=withdrawn,
        guard=guard if guard is not None else InProcessGuard(),
        trusted=frozenset(),
    )


def test_a_token_this_issuer_signed_is_answered() -> None:
    assert _access().decide(_token(), "1.2.3.4").allowed


def test_a_request_with_no_token_is_not_answered() -> None:
    assert _access().decide(None, "1.2.3.4").outcome is Outcome.UNAUTHENTICATED


def test_every_way_of_not_being_answered_reads_the_same() -> None:
    from wiki_api.access.tokens import assemble, claims

    refusals = {
        _access().decide(None, "a").outcome,
        _access().decide("nonsense", "b").outcome,
        _access().decide(assemble(claims("x", "y"), b"0" * 64), "c").outcome,
        _access(withdrawn=frozenset({"abcd"})).decide(_token(), "d").outcome,
    }
    assert refusals == {Outcome.UNAUTHENTICATED}


def test_a_caller_that_keeps_trying_is_shut_out() -> None:
    guard = InProcessGuard(most_refusals=2)
    access = _access(guard=guard)
    access.decide("nonsense", "1.2.3.4")
    access.decide("nonsense", "1.2.3.4")
    decision = access.decide(_token(), "1.2.3.4")
    assert decision.outcome is Outcome.BLOCKED
    assert decision.after is not None


def test_a_caller_past_its_share_is_told_when_to_come_back() -> None:
    access = _access(guard=InProcessGuard(burst=1, rate=0.0))
    assert access.decide(_token(), "1.2.3.4").allowed
    decision = access.decide(_token(), "1.2.3.4")
    assert decision.outcome is Outcome.THROTTLED
    assert decision.after is not None


def test_being_over_a_share_is_never_treated_as_an_attack() -> None:
    access = _access(guard=InProcessGuard(burst=1, rate=0.0, most_refusals=1))
    access.decide(_token(), "1.2.3.4")
    access.decide(_token(), "1.2.3.4")
    assert access.decide(_token(), "1.2.3.4").outcome is Outcome.THROTTLED


def test_the_socket_address_is_who_is_held_responsible() -> None:
    assert caller_of("1.2.3.4", "9.9.9.9", frozenset()) == "1.2.3.4"


def test_a_forwarded_address_counts_only_from_a_proxy_we_named() -> None:
    assert caller_of("1.2.3.4", "9.9.9.9", frozenset({"1.2.3.4"})) == "9.9.9.9"


def test_the_nearest_hop_is_the_one_a_proxy_is_believed_about() -> None:
    forwarded = "8.8.8.8, 9.9.9.9"
    assert caller_of("1.2.3.4", forwarded, frozenset({"1.2.3.4"})) == "9.9.9.9"


def test_a_request_from_nowhere_is_still_somebody() -> None:
    assert caller_of(None, None, frozenset()) == UNKNOWN_CALLER


def test_a_health_check_is_the_only_thing_answered_without_a_token() -> None:
    assert anonymous("/health") is True
    assert anonymous("/v1/about") is False
    assert anonymous("/v1/entities/item/4587") is False


def test_a_deployment_that_answers_everyone_has_nothing_to_decide() -> None:
    from wiki_api.config import Settings

    assert access_from(Settings(auth_mode="off")) is None


def test_a_deployment_that_answers_holders_needs_a_key_to_check_with(
    tmp_path: Path, monkeypatch: object
) -> None:
    import pytest

    from wiki_api.access.paths import CONFIG_DIR_VARIABLE
    from wiki_api.config import Settings

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    monkeypatch.setenv(CONFIG_DIR_VARIABLE, str(tmp_path / "nothing"))
    unchecked = Settings.model_construct(
        auth_mode="required", auth_public_key="", auth_public_key_file=None
    )
    with pytest.raises(AccessMisconfigured):
        access_from(unchecked)


def _guarded(tmp_path: object, **given: object) -> Settings:
    """Build settings for a guarded deployment keeping its files under a test path."""
    from pathlib import Path

    from wiki_api.access import public_key_text
    from wiki_api.config import Settings

    assert isinstance(tmp_path, Path)
    _, public_key = _keys()
    asked: dict[str, object] = {
        "auth_mode": "required",
        "auth_public_key": public_key_text(public_key),
        "cors_origins": ("https://wiki.example.test",),
        "ban_file": tmp_path / "banned.json",
        **given,
    }
    return Settings(**asked)  # type: ignore[arg-type]


def test_a_key_kept_in_a_file_is_read_from_it(tmp_path: object) -> None:
    from pathlib import Path

    from wiki_api.access import public_key_text

    assert isinstance(tmp_path, Path)
    _, public_key = _keys()
    written = tmp_path / "issuer.pub"
    written.write_text(public_key_text(public_key), encoding="utf-8")
    access = access_from(
        _guarded(tmp_path, auth_public_key="", auth_public_key_file=written)
    )
    assert access is not None
    assert access.decide(_token(), "1.2.3.4").allowed


def test_a_configured_key_is_the_one_tokens_are_checked_against(
    tmp_path: object,
) -> None:
    access = access_from(_guarded(tmp_path))
    assert access is not None
    assert access.decide(_token(), "1.2.3.4").allowed


def test_who_is_shut_out_is_written_where_the_deployment_says(
    tmp_path: object,
) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    written = tmp_path / "banned.json"
    access = access_from(_guarded(tmp_path))
    assert access is not None
    assert written.exists()


def test_who_is_shut_out_is_kept_beside_the_keys_when_nothing_says_otherwise(
    monkeypatch: object, tmp_path: object
) -> None:
    from pathlib import Path

    import pytest

    from wiki_api.access.paths import CONFIG_DIR_VARIABLE, banned_path

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(tmp_path, Path)
    monkeypatch.setenv(CONFIG_DIR_VARIABLE, str(tmp_path / "elsewhere"))
    settings = _guarded(tmp_path).model_copy(update={"ban_file": None})
    assert access_from(settings) is not None
    assert banned_path(tmp_path / "elsewhere").exists()
