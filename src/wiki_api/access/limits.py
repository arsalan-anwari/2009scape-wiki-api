"""Decide how much one caller may ask for, and shut out an address whose tokens keep
failing to verify.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING, Final, Protocol

from wiki_api.access.bans import Bans, RememberedBans

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

RATE_PER_SECOND: Final = 10.0
RATE_BURST: Final = 60
MAX_REFUSALS: Final = 10
REFUSAL_WINDOW: Final = 60.0
BAN_SECONDS: Final = 900.0
LONGEST_BAN: Final = 86_400.0
TRACKED_CALLERS: Final = 10_000


@dataclass(frozen=True)
class Allowed:
    """This request may be answered."""


@dataclass(frozen=True)
class Throttled:
    """This caller has asked for more than its share; `after` is when to come back."""

    after: int


@dataclass(frozen=True)
class ShutOut:
    """This address is not being answered at all right now."""

    after: int


Ruling = Allowed | Throttled | ShutOut


class Guard(Protocol):
    """Whatever decides how much a caller may ask for and who is shut out."""

    def admits(self, kid: str) -> Ruling: ...

    def shut_out(self, caller: str) -> Ruling: ...

    def refused(self, caller: str) -> None: ...


@dataclass
class _Bucket:
    tokens: float
    at: float


@dataclass
class _Recent:
    count: int = 0
    since: float = 0.0


class InProcessGuard:
    """A guard that remembers in this process and nowhere else."""

    def __init__(
        self,
        *,
        rate: float = RATE_PER_SECOND,
        burst: int = RATE_BURST,
        most_refusals: int = MAX_REFUSALS,
        window: float = REFUSAL_WINDOW,
        ban: float = BAN_SECONDS,
        longest_ban: float = LONGEST_BAN,
        tracked: int = TRACKED_CALLERS,
        now: Callable[[], float] | None = None,
        bans: Bans | None = None,
    ) -> None:
        self._rate = rate
        self._burst = burst
        self._most_refusals = most_refusals
        self._window = window
        self._ban = ban
        self._longest_ban = longest_ban
        self._tracked = tracked
        self._now = now if now is not None else time.monotonic
        self._bans = bans if bans is not None else RememberedBans(most=tracked)
        self._buckets: dict[str, _Bucket] = {}
        self._recent: dict[str, _Recent] = {}

    def admits(self, kid: str) -> Ruling:
        """Whether this key has any of its share left."""
        at = self._now()
        bucket = self._buckets.get(kid)
        if bucket is None:
            bucket = _Bucket(tokens=float(self._burst), at=at)
            self._buckets[kid] = bucket
            self._forget_shares()
        bucket.tokens = min(
            float(self._burst), bucket.tokens + (at - bucket.at) * self._rate
        )
        bucket.at = at
        if bucket.tokens < 1.0:
            return Throttled(after=self._refill_of(1.0 - bucket.tokens))
        bucket.tokens -= 1.0
        return Allowed()

    def shut_out(self, caller: str) -> Ruling:
        """Whether this address is currently being ignored."""
        left = self._bans.left(caller)
        if left is None:
            return Allowed()
        return ShutOut(after=max(1, ceil(left)))

    def refused(self, caller: str) -> None:
        """Record that this address presented something that did not verify."""
        at = self._now()
        recent = self._recent.get(caller)
        if recent is None or at - recent.since > self._window:
            recent = _Recent(since=at)
            self._recent[caller] = recent
            self._forget_recent()
        recent.count += 1
        if recent.count < self._most_refusals:
            return
        del self._recent[caller]
        self._bans.shut_out(
            caller,
            min(self._longest_ban, self._ban * (2 ** self._bans.strikes(caller))),
        )

    def tracking(self) -> tuple[int, int]:
        """How many callers and how many addresses are being remembered."""
        return len(self._buckets), len(self._recent)

    def bans(self) -> Bans:
        """Wherever the shut-out addresses are being kept."""
        return self._bans

    def _refill_of(self, shortfall: float) -> int:
        if self._rate <= 0.0:
            return max(1, ceil(self._ban))
        return max(1, ceil(shortfall / self._rate))

    def _forget_shares(self) -> None:
        while len(self._buckets) > self._tracked:
            del self._buckets[next(iter(self._buckets))]

    def _forget_recent(self) -> None:
        """Drop the oldest refusal counts once more than `tracked` are held."""
        while len(self._recent) > self._tracked:
            del self._recent[next(iter(self._recent))]


# test cases


class _Clock:
    def __init__(self) -> None:
        self.at = 0.0

    def __call__(self) -> float:
        return self.at

    def tick(self, seconds: float) -> None:
        self.at += seconds


def _guarding(clock: _Clock, **given: float | int) -> InProcessGuard:
    """Build a guard whose share clock and ban clock are the same `clock`."""
    return InProcessGuard(
        now=clock,
        bans=RememberedBans(clock=clock),
        **given,  # type: ignore[arg-type]
    )


def test_a_caller_within_its_share_is_answered() -> None:
    guard = InProcessGuard(now=_Clock())
    assert guard.admits("one") == Allowed()


def test_a_caller_that_empties_its_share_is_told_to_wait() -> None:
    clock = _Clock()
    guard = InProcessGuard(burst=2, rate=1.0, now=clock)
    assert guard.admits("one") == Allowed()
    assert guard.admits("one") == Allowed()
    ruling = guard.admits("one")
    assert isinstance(ruling, Throttled)
    assert ruling.after >= 1


def test_a_share_fills_back_up_as_time_passes() -> None:
    clock = _Clock()
    guard = InProcessGuard(burst=1, rate=1.0, now=clock)
    assert guard.admits("one") == Allowed()
    assert isinstance(guard.admits("one"), Throttled)
    clock.tick(1.0)
    assert guard.admits("one") == Allowed()


def test_a_share_never_fills_past_what_it_holds() -> None:
    clock = _Clock()
    guard = InProcessGuard(burst=2, rate=1.0, now=clock)
    clock.tick(1_000.0)
    assert guard.admits("one") == Allowed()
    assert guard.admits("one") == Allowed()
    assert isinstance(guard.admits("one"), Throttled)


def test_one_callers_share_is_not_anothers() -> None:
    guard = InProcessGuard(burst=1, rate=0.0, now=_Clock())
    assert guard.admits("one") == Allowed()
    assert guard.admits("two") == Allowed()


def test_an_address_that_has_done_nothing_wrong_is_answered() -> None:
    assert _guarding(_Clock()).shut_out("1.2.3.4") == Allowed()


def test_enough_refusals_shut_an_address_out() -> None:
    clock = _Clock()
    guard = _guarding(clock, most_refusals=3)
    for _ in range(3):
        guard.refused("1.2.3.4")
    ruling = guard.shut_out("1.2.3.4")
    assert isinstance(ruling, ShutOut)
    assert ruling.after > 0


def test_being_shut_out_wears_off() -> None:
    clock = _Clock()
    guard = _guarding(clock, most_refusals=2, ban=10.0)
    guard.refused("1.2.3.4")
    guard.refused("1.2.3.4")
    assert isinstance(guard.shut_out("1.2.3.4"), ShutOut)
    clock.tick(11.0)
    assert guard.shut_out("1.2.3.4") == Allowed()


def test_coming_back_to_try_again_costs_longer_each_time() -> None:
    clock = _Clock()
    guard = _guarding(clock, most_refusals=2, ban=10.0)
    for _ in range(2):
        guard.refused("1.2.3.4")
    first = guard.shut_out("1.2.3.4")
    clock.tick(11.0)
    for _ in range(2):
        guard.refused("1.2.3.4")
    second = guard.shut_out("1.2.3.4")
    assert isinstance(first, ShutOut)
    assert isinstance(second, ShutOut)
    assert second.after > first.after


def test_a_ban_never_grows_past_what_was_allowed_for() -> None:
    clock = _Clock()
    guard = _guarding(clock, most_refusals=1, ban=10.0, longest_ban=15.0)
    for _ in range(8):
        guard.refused("1.2.3.4")
    ruling = guard.shut_out("1.2.3.4")
    assert isinstance(ruling, ShutOut)
    assert ruling.after <= 15


def test_refusals_spread_thinly_enough_never_add_up() -> None:
    clock = _Clock()
    guard = _guarding(clock, most_refusals=3, window=60.0)
    for _ in range(10):
        guard.refused("1.2.3.4")
        clock.tick(61.0)
    assert guard.shut_out("1.2.3.4") == Allowed()


def test_one_addresss_behaviour_never_shuts_out_another() -> None:
    guard = _guarding(_Clock(), most_refusals=1)
    guard.refused("1.2.3.4")
    assert guard.shut_out("5.6.7.8") == Allowed()


def test_what_is_remembered_about_callers_is_bounded() -> None:
    guard = _guarding(_Clock(), tracked=16, most_refusals=100)
    for number in range(500):
        guard.admits(f"key-{number}")
        guard.refused(f"{number}.0.0.1")
    assert guard.tracking() == (16, 16)


def test_inventing_addresses_is_never_a_way_out_of_being_shut_out() -> None:
    clock = _Clock()
    guard = _guarding(clock, tracked=4, most_refusals=2, ban=1_000.0)
    guard.refused("1.2.3.4")
    guard.refused("1.2.3.4")
    for number in range(200):
        guard.refused(f"{number}.9.9.9")
    assert isinstance(guard.shut_out("1.2.3.4"), ShutOut)


def test_a_throttled_caller_is_never_shut_out_for_it() -> None:
    guard = _guarding(_Clock(), burst=1, rate=0.0, most_refusals=1)
    guard.admits("one")
    assert isinstance(guard.admits("one"), Throttled)
    assert guard.shut_out("1.2.3.4") == Allowed()


def test_the_guard_is_whatever_satisfies_the_protocol() -> None:
    guard: Guard = InProcessGuard()
    assert isinstance(guard.admits("one"), Allowed)


def test_a_ban_outlives_the_guard_that_made_it(tmp_path: Path) -> None:
    from wiki_api.access.bans import FileBans

    clock = _Clock()
    clock.tick(1_800_000_000.0)
    path = tmp_path / "banned.json"
    first = InProcessGuard(most_refusals=2, now=clock, bans=FileBans(path, clock=clock))
    first.refused("1.2.3.4")
    first.refused("1.2.3.4")
    assert isinstance(first.shut_out("1.2.3.4"), ShutOut)

    started_again = InProcessGuard(now=clock, bans=FileBans(path, clock=clock))
    assert isinstance(started_again.shut_out("1.2.3.4"), ShutOut)


def test_a_share_is_never_written_down(tmp_path: Path) -> None:
    from wiki_api.access.bans import FileBans

    clock = _Clock()
    clock.tick(1_800_000_000.0)
    path = tmp_path / "banned.json"
    guard = InProcessGuard(
        burst=1, rate=0.0, now=clock, bans=FileBans(path, clock=clock)
    )
    guard.admits("one")
    assert isinstance(guard.admits("one"), Throttled)

    started_again = InProcessGuard(
        burst=1, rate=0.0, now=clock, bans=FileBans(path, clock=clock)
    )
    assert started_again.admits("one") == Allowed()
