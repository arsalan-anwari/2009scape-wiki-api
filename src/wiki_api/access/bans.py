"""Keep the addresses that are not being answered"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Protocol

from wiki_api.access.errors import AccessMisconfigured

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

VERSION: Final = 1
MOST_BANS: Final = 10_000


@dataclass(frozen=True)
class Ban:
    """One address that is not being answered, and how many times it has been here."""

    caller: str
    until: float
    strikes: int

    @property
    def at(self) -> datetime:
        """When this ban lifts, as something a person can read."""
        return datetime.fromtimestamp(self.until, tz=UTC)


class Bans(Protocol):
    """Wherever the shut-out addresses are kept."""

    def left(self, caller: str) -> float | None: ...

    def strikes(self, caller: str) -> int: ...

    def shut_out(self, caller: str, seconds: float) -> None: ...

    def lift(self, caller: str) -> bool: ...

    def listed(self) -> tuple[Ban, ...]: ...


class RememberedBans:
    """Shut-out addresses held in this process and nowhere else."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        most: int = MOST_BANS,
    ) -> None:
        self._clock = clock if clock is not None else _wall_clock
        self._most = most
        self._held: dict[str, Ban] = {}

    def left(self, caller: str) -> float | None:
        """How long until this address is answered again, or nothing when it is."""
        self._refresh()
        ban = self._held.get(caller)
        if ban is None:
            return None
        left = ban.until - self._clock()
        return left if left > 0.0 else None

    def strikes(self, caller: str) -> int:
        """How many times this address has been shut out, lapsed bans included."""
        self._refresh()
        ban = self._held.get(caller)
        return ban.strikes if ban is not None else 0

    def shut_out(self, caller: str, seconds: float) -> None:
        """Stop answering this address for that long, starting now."""
        self._refresh()
        self._held[caller] = Ban(
            caller=caller,
            until=self._clock() + seconds,
            strikes=self.strikes(caller) + 1,
        )
        self._crop()
        self._changed()

    def lift(self, caller: str) -> bool:
        """Answer this address again, and say whether it was being refused."""
        self._refresh()
        if self._held.pop(caller, None) is None:
            return False
        self._changed()
        return True

    def listed(self) -> tuple[Ban, ...]:
        """Every address currently shut out, soonest to be answered first."""
        self._refresh()
        at = self._clock()
        return tuple(
            sorted(
                (ban for ban in self._held.values() if ban.until > at),
                key=lambda ban: (ban.until, ban.caller),
            )
        )

    def _refresh(self) -> None:
        return None

    def _changed(self) -> None:
        return None

    def _crop(self) -> None:
        """Drop bans past `most`, lapsed ones first.

        Lapsed first, so filling this up with invented addresses never clears a ban
        still in force.
        """
        if len(self._held) <= self._most:
            return
        at = self._clock()
        for caller, ban in list(self._held.items()):
            if len(self._held) <= self._most:
                return
            if ban.until <= at:
                del self._held[caller]
        while len(self._held) > self._most:
            soonest = min(self._held.values(), key=lambda ban: ban.until)
            del self._held[soonest.caller]


class FileBans(RememberedBans):
    """Shut-out addresses written down, so a restart does not answer them again."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], float] | None = None,
        most: int = MOST_BANS,
    ) -> None:
        super().__init__(clock=clock, most=most)
        self._path = path
        self._read_at: tuple[int, int] | None = None
        self._load()
        self._save(loudly=True)

    @property
    def path(self) -> Path:
        """The file this list is kept in."""
        return self._path

    def _refresh(self) -> None:
        if self._stamp() != self._read_at:
            self._load()

    def _changed(self) -> None:
        self._save()

    def _load(self) -> None:
        self._read_at = self._stamp()
        if not self._path.exists():
            return
        try:
            written = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AccessMisconfigured(
                f"the list of shut-out addresses in {self._path} is not readable"
            ) from error
        self._held = {ban.caller: ban for ban in _read(written)}

    def _save(self, *, loudly: bool = False) -> None:
        """Write the list out through a rename, so a reader never sees half of it.

        With `loudly`, a failed write raises; otherwise it is swallowed and the ban
        stands in this process only.
        """
        at = self._clock()
        kept = sorted(
            (ban for ban in self._held.values() if ban.until > at),
            key=lambda ban: (ban.until, ban.caller),
        )
        beside = self._path.with_name(f"{self._path.name}.writing")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            beside.write_text(_written(kept), encoding="utf-8")
            os.replace(beside, self._path)
        except OSError as error:
            if loudly:
                raise AccessMisconfigured(
                    f"the list of shut-out addresses in {self._path} cannot be written"
                ) from error
            return
        self._read_at = self._stamp()

    def _stamp(self) -> tuple[int, int] | None:
        try:
            found = self._path.stat()
        except OSError:
            return None
        return found.st_mtime_ns, found.st_size


def _written(bans: Iterable[Ban]) -> str:
    return (
        json.dumps(
            {
                "version": VERSION,
                "banned": [
                    {
                        "caller": ban.caller,
                        "until": ban.at.isoformat(),
                        "strikes": ban.strikes,
                    }
                    for ban in bans
                ],
            },
            indent=2,
        )
        + "\n"
    )


def _read(written: object) -> tuple[Ban, ...]:
    if not isinstance(written, dict) or written.get("version") != VERSION:
        raise AccessMisconfigured(
            "the list of shut-out addresses is written in a version we cannot read"
        )
    listed = written.get("banned")
    if not isinstance(listed, list):
        raise AccessMisconfigured("the list of shut-out addresses is not a list")
    return tuple(_one(entry) for entry in listed)


def _one(entry: object) -> Ban:
    if not isinstance(entry, dict):
        raise AccessMisconfigured("a shut-out address is not written as one")
    caller = entry.get("caller")
    until = entry.get("until")
    strikes = entry.get("strikes", 1)
    if not isinstance(caller, str) or not isinstance(until, str):
        raise AccessMisconfigured("a shut-out address is missing who or until when")
    try:
        moment = datetime.fromisoformat(until)
    except ValueError as error:
        raise AccessMisconfigured(
            "a shut-out address has an unreadable time"
        ) from error
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return Ban(
        caller=caller,
        until=moment.timestamp(),
        strikes=strikes if isinstance(strikes, int) and strikes > 0 else 1,
    )


def _wall_clock() -> float:
    import time

    return time.time()


# test cases


class _Clock:
    def __init__(self, at: float = 1_800_000_000.0) -> None:
        self.at = at

    def __call__(self) -> float:
        return self.at

    def tick(self, seconds: float) -> None:
        self.at += seconds


def test_an_address_nobody_shut_out_is_answered() -> None:
    assert RememberedBans(clock=_Clock()).left("1.2.3.4") is None


def test_a_shut_out_address_says_how_long_it_has_to_wait() -> None:
    bans = RememberedBans(clock=_Clock())
    bans.shut_out("1.2.3.4", 900.0)
    assert bans.left("1.2.3.4") == 900.0


def test_a_ban_wears_off_on_its_own() -> None:
    clock = _Clock()
    bans = RememberedBans(clock=clock)
    bans.shut_out("1.2.3.4", 10.0)
    clock.tick(11.0)
    assert bans.left("1.2.3.4") is None


def test_coming_back_is_counted_even_after_a_ban_lapsed() -> None:
    clock = _Clock()
    bans = RememberedBans(clock=clock)
    bans.shut_out("1.2.3.4", 10.0)
    clock.tick(11.0)
    bans.shut_out("1.2.3.4", 10.0)
    assert bans.strikes("1.2.3.4") == 2


def test_an_address_can_be_answered_again_on_purpose() -> None:
    bans = RememberedBans(clock=_Clock())
    bans.shut_out("1.2.3.4", 900.0)
    assert bans.lift("1.2.3.4") is True
    assert bans.left("1.2.3.4") is None


def test_lifting_a_ban_nobody_has_says_so() -> None:
    assert RememberedBans(clock=_Clock()).lift("1.2.3.4") is False


def test_only_the_addresses_still_shut_out_are_listed() -> None:
    clock = _Clock()
    bans = RememberedBans(clock=clock)
    bans.shut_out("1.2.3.4", 10.0)
    bans.shut_out("5.6.7.8", 100.0)
    clock.tick(11.0)
    assert [ban.caller for ban in bans.listed()] == ["5.6.7.8"]


def test_what_is_remembered_is_bounded() -> None:
    bans = RememberedBans(clock=_Clock(), most=8)
    for number in range(200):
        bans.shut_out(f"{number}.0.0.1", 900.0)
    assert len(bans.listed()) <= 8


def test_a_lapsed_ban_is_dropped_before_one_still_in_force() -> None:
    clock = _Clock()
    bans = RememberedBans(clock=clock, most=4)
    bans.shut_out("1.2.3.4", 10_000.0)
    clock.tick(1.0)
    for number in range(20):
        bans.shut_out(f"{number}.9.9.9", 1.0)
        clock.tick(2.0)
    assert bans.left("1.2.3.4") is not None


def test_a_ban_written_down_survives_the_process(tmp_path: Path) -> None:
    clock = _Clock()
    path = tmp_path / "banned.json"
    FileBans(path, clock=clock).shut_out("1.2.3.4", 900.0)
    assert FileBans(path, clock=clock).left("1.2.3.4") == 900.0


def test_a_ban_that_lapsed_while_nothing_was_running_is_not_revived(
    tmp_path: Path,
) -> None:
    clock = _Clock()
    path = tmp_path / "banned.json"
    FileBans(path, clock=clock).shut_out("1.2.3.4", 10.0)
    clock.tick(11.0)
    assert FileBans(path, clock=clock).left("1.2.3.4") is None


def test_what_is_written_down_is_readable_by_a_person(tmp_path: Path) -> None:
    path = tmp_path / "banned.json"
    FileBans(path, clock=_Clock()).shut_out("1.2.3.4", 900.0)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["version"] == VERSION
    assert written["banned"][0]["caller"] == "1.2.3.4"
    assert written["banned"][0]["until"].startswith("20")


def test_a_ban_lifted_by_hand_stops_being_a_ban(tmp_path: Path) -> None:
    clock = _Clock()
    path = tmp_path / "banned.json"
    bans = FileBans(path, clock=clock)
    bans.shut_out("1.2.3.4", 900.0)
    path.write_text(_written(()), encoding="utf-8")
    assert bans.left("1.2.3.4") is None


def test_a_ban_made_by_something_else_is_honoured_here(tmp_path: Path) -> None:
    clock = _Clock()
    path = tmp_path / "banned.json"
    here = FileBans(path, clock=clock)
    elsewhere = FileBans(path, clock=clock)
    elsewhere.shut_out("1.2.3.4", 900.0)
    assert here.left("1.2.3.4") == 900.0


def test_a_file_full_of_nonsense_is_never_read_as_nobody_being_banned(
    tmp_path: Path,
) -> None:
    import pytest

    path = tmp_path / "banned.json"
    for junk in ("not json", "[]", '{"version": 99, "banned": []}', '{"version": 1}'):
        path.write_text(junk, encoding="utf-8")
        with pytest.raises(AccessMisconfigured):
            FileBans(path, clock=_Clock())


def test_a_banned_address_that_says_nothing_useful_is_refused(
    tmp_path: Path,
) -> None:
    import pytest

    path = tmp_path / "banned.json"
    missing = ('[{"caller": "a"}]', '[{"until": "2030-01-01T00:00:00+00:00"}]', "[7]")
    for junk in missing:
        path.write_text(f'{{"version": 1, "banned": {junk}}}', encoding="utf-8")
        with pytest.raises(AccessMisconfigured):
            FileBans(path, clock=_Clock())


def test_a_place_that_cannot_be_written_to_says_so_at_once(tmp_path: Path) -> None:
    import pytest

    unwritable = tmp_path / "wall"
    unwritable.write_text("in the way", encoding="utf-8")
    with pytest.raises(AccessMisconfigured):
        FileBans(unwritable / "banned.json", clock=_Clock())


def test_nothing_is_left_behind_beside_the_list(tmp_path: Path) -> None:
    path = tmp_path / "banned.json"
    FileBans(path, clock=_Clock()).shut_out("1.2.3.4", 900.0)
    assert [found.name for found in tmp_path.iterdir()] == ["banned.json"]


def test_whatever_keeps_the_bans_satisfies_the_one_interface(tmp_path: Path) -> None:
    held: Bans = RememberedBans(clock=_Clock())
    written: Bans = FileBans(tmp_path / "banned.json", clock=_Clock())
    assert held.listed() == ()
    assert written.listed() == ()
