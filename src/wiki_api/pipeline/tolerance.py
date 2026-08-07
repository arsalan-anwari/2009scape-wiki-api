"""How much of a source may go unread, declared once so a build can refuse more."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.artifact.errors import BuildError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


class ToleranceExceeded(BuildError):
    """A source left more unread than it is allowed to."""

    def __init__(self, source: str, reason: str, found: int, allowed: int) -> None:
        super().__init__(
            f"{source} left {found} rows unread as {reason}, "
            f"which is more than the {allowed} this build tolerates"
        )
        self.source = source
        self.reason = reason
        self.found = found
        self.allowed = allowed


class Tolerance(BaseModel):
    """One declared ceiling: how much of one source may be unreadable, and why."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    allowed: int = Field(ge=0)
    because: str = Field(min_length=1)

    def check(self, found: int) -> None:
        """Refuse a count above the ceiling this tolerance declares."""
        if found > self.allowed:
            raise ToleranceExceeded(self.source, self.reason, found, self.allowed)

    def line(self, found: int) -> str:
        return f"{self.source}: {found} of {self.allowed} allowed ({self.reason})"


DECLARED_TOLERANCES: Final[tuple[Tolerance, ...]] = (
    Tolerance(
        source="cache/placements",
        reason="region did not open",
        allowed=330,
        because=(
            "1229 regions, 1122 keys, and 318 that the game cannot open either: "
            "68 have no key at all and 250 have one that does not work"
        ),
    ),
    Tolerance(
        source="cache/npcs",
        reason="definition refused",
        allowed=5,
        because="npc 3352 carries opcode 138, which the game's own decoder drops",
    ),
    Tolerance(
        source="cache/items",
        reason="definition refused",
        allowed=0,
        because="every item definition decodes today, so any refusal is new",
    ),
    Tolerance(
        source="cache/scenery",
        reason="definition refused",
        allowed=0,
        because="every scenery definition decodes today, so any refusal is new",
    ),
)


def tolerance_for(
    source: str, tolerances: Sequence[Tolerance] = DECLARED_TOLERANCES
) -> Tolerance | None:
    """The declared ceiling for one source, where there is one."""
    for declared in tolerances:
        if declared.source == source:
            return declared
    return None


def check_tolerances(
    counted: Mapping[str, int], tolerances: Sequence[Tolerance] = DECLARED_TOLERANCES
) -> tuple[str, ...]:
    """Refuse any source over its ceiling, and report every source that has one."""
    told: list[str] = []
    for source, found in sorted(counted.items()):
        declared = tolerance_for(source, tolerances)
        if declared is None:
            continue
        declared.check(found)
        told.append(declared.line(found))
    return tuple(told)


def undeclared(
    sources: Iterable[str], tolerances: Sequence[Tolerance] = DECLARED_TOLERANCES
) -> tuple[str, ...]:
    """The sources that reported something unread and have no ceiling declared."""
    return tuple(
        sorted(name for name in sources if tolerance_for(name, tolerances) is None)
    )


# test cases


def _tolerance(**overrides: object) -> Tolerance:
    payload: dict[str, object] = {
        "source": "cache/placements",
        "reason": "region did not open",
        "allowed": 2,
        "because": "two regions have no key",
    }
    payload.update(overrides)
    return Tolerance.model_validate(payload)


def test_a_count_inside_the_ceiling_passes() -> None:
    _tolerance().check(2)


def test_a_count_above_the_ceiling_names_the_source_and_both_numbers() -> None:
    import pytest

    with pytest.raises(ToleranceExceeded) as caught:
        _tolerance().check(3)
    assert "cache/placements" in str(caught.value)
    assert caught.value.found == 3
    assert caught.value.allowed == 2


def test_every_declared_source_is_checked_and_reported() -> None:
    told = check_tolerances(
        {"cache/placements": 1, "cache/items": 0}, tolerances=(_tolerance(),)
    )
    assert told == ("cache/placements: 1 of 2 allowed (region did not open)",)


def test_a_source_with_no_ceiling_is_named_rather_than_ignored() -> None:
    assert undeclared(["cache/items"], tolerances=(_tolerance(),)) == ("cache/items",)
    assert undeclared(["cache/placements"], tolerances=(_tolerance(),)) == ()


def test_every_declared_tolerance_says_why_it_is_what_it_is() -> None:
    assert all(declared.because for declared in DECLARED_TOLERANCES)
    assert len({declared.source for declared in DECLARED_TOLERANCES}) == len(
        DECLARED_TOLERANCES
    )


def test_the_map_ceiling_covers_what_the_game_cannot_open_either() -> None:
    declared = tolerance_for("cache/placements")
    assert declared is not None
    assert declared.allowed >= 318
