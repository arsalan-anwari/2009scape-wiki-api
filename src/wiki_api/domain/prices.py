"""Grand Exchange price history, and what a series of it is worth believing."""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.vocabulary import PriceConfidence

if TYPE_CHECKING:
    from collections.abc import Sequence

NO_MARKET: Final = 1


class PricePoint(BaseModel):
    """What one item was worth on one snapshot day."""

    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=0)
    snapshot_date: date
    value: int = Field(ge=0)


class PriceSummary(BaseModel):
    """A whole price series read down to what it takes to decide whether to trust it."""

    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=0)
    latest: int = Field(ge=0)
    as_of: date
    low: int = Field(ge=0)
    high: int = Field(ge=0)
    mean: int = Field(ge=0)
    middle: int = Field(ge=0)
    entries: int = Field(ge=1)
    confidence: PriceConfidence


class PriceMovement(BaseModel):
    """Which way a price went over a stretch of the record, and by how much."""

    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=0)
    opened: int = Field(ge=0)
    opened_on: date
    closed: int = Field(ge=0)
    closed_on: date
    low: int = Field(ge=0)
    high: int = Field(ge=0)
    entries: int = Field(ge=1)
    change: int
    confidence: PriceConfidence

    @property
    def share(self) -> float:
        """The change as a share of what it opened at, zero from a standing start."""
        if self.opened == 0:
            return 0.0
        return self.change / self.opened


def latest_price(points: Sequence[PricePoint]) -> PricePoint | None:
    """The newest of the given points, or None when there are none."""
    if not points:
        return None
    return max(points, key=lambda point: point.snapshot_date)


def confidence_of(values: Sequence[int]) -> PriceConfidence:
    """Judge a series by whether it ever moved and whether it ever left the floor."""
    if max(values) <= NO_MARKET:
        return PriceConfidence.UNTRADED
    if min(values) == max(values):
        return PriceConfidence.STATIC
    return PriceConfidence.TRADED


def summarise(points: Sequence[PricePoint]) -> PriceSummary | None:
    """Read a whole series down to one summary, or nothing when there is no series."""
    newest = latest_price(points)
    if newest is None:
        return None
    values = [point.value for point in points]
    return PriceSummary(
        item_id=newest.item_id,
        latest=newest.value,
        as_of=newest.snapshot_date,
        low=min(values),
        high=max(values),
        mean=round(sum(values) / len(values)),
        middle=round(median(values)),
        entries=len(values),
        confidence=confidence_of(values),
    )


def moved(points: Sequence[PricePoint]) -> PriceMovement | None:
    """Read a stretch of the record down to which way it went, or nothing when it holds
    no readings.
    """
    if not points:
        return None
    ordered = sorted(points, key=lambda point: point.snapshot_date)
    opened, closed = ordered[0], ordered[-1]
    values = [point.value for point in ordered]
    return PriceMovement(
        item_id=closed.item_id,
        opened=opened.value,
        opened_on=opened.snapshot_date,
        closed=closed.value,
        closed_on=closed.snapshot_date,
        low=min(values),
        high=max(values),
        entries=len(values),
        change=closed.value - opened.value,
        confidence=confidence_of(values),
    )


# test cases


def test_a_price_point_pins_a_value_to_a_date() -> None:
    point = PricePoint(item_id=4587, snapshot_date=date(2024, 6, 8), value=106049)
    assert point.value == 106049


def test_the_latest_price_is_the_newest_snapshot() -> None:
    points = [
        PricePoint(item_id=4587, snapshot_date=date(2024, 6, 8), value=106049),
        PricePoint(item_id=4587, snapshot_date=date(2024, 6, 22), value=106500),
        PricePoint(item_id=4587, snapshot_date=date(2024, 6, 15), value=106049),
    ]
    newest = latest_price(points)
    assert newest is not None
    assert newest.snapshot_date == date(2024, 6, 22)


def test_an_unpriced_item_has_no_latest_price() -> None:
    assert latest_price([]) is None


def test_negative_prices_are_rejected() -> None:
    import pytest

    with pytest.raises(ValueError):
        PricePoint(item_id=4587, snapshot_date=date(2024, 6, 8), value=-1)


def _series(*values: int) -> list[PricePoint]:
    return [
        PricePoint(item_id=4587, snapshot_date=date(2024, 6, 8 + day), value=value)
        for day, value in enumerate(values)
    ]


def test_a_series_that_moves_is_worth_believing() -> None:
    assert confidence_of([100, 120, 110]) is PriceConfidence.TRADED


def test_a_series_that_never_moved_is_a_listed_price_not_a_traded_one() -> None:
    assert confidence_of([500, 500, 500]) is PriceConfidence.STATIC


def test_a_series_that_never_left_the_floor_says_there_is_no_market() -> None:
    assert confidence_of([1, 1, 1]) is PriceConfidence.UNTRADED
    assert confidence_of([0, 1]) is PriceConfidence.UNTRADED


def test_an_item_that_reached_a_real_price_is_not_called_untraded() -> None:
    assert confidence_of([1, 1, 10_000_000]) is PriceConfidence.TRADED


def test_a_summary_carries_the_newest_price_and_the_day_it_held() -> None:
    summary = summarise(_series(100, 300, 200))
    assert summary is not None
    assert summary.latest == 200
    assert summary.as_of == date(2024, 6, 10)


def test_a_summary_carries_the_spread_a_reader_judges_it_by() -> None:
    summary = summarise(_series(100, 300, 200))
    assert summary is not None
    assert (summary.low, summary.high, summary.mean, summary.middle) == (
        100,
        300,
        200,
        200,
    )
    assert summary.entries == 3


def test_a_summary_says_how_far_to_trust_itself() -> None:
    summary = summarise(_series(1, 1, 1))
    assert summary is not None
    assert summary.confidence is PriceConfidence.UNTRADED


def test_an_item_with_no_snapshots_gets_no_summary() -> None:
    assert summarise([]) is None


def test_a_movement_answers_which_way_the_price_went() -> None:
    movement = moved(_series(100, 300, 200))
    assert movement is not None
    assert (movement.opened, movement.closed, movement.change) == (100, 200, 100)
    assert movement.share == 1.0


def test_a_price_that_fell_says_so_with_a_negative_change() -> None:
    movement = moved(_series(200, 50))
    assert movement is not None
    assert movement.change == -150
    assert movement.share == -0.75


def test_a_movement_names_the_days_it_was_read_between() -> None:
    movement = moved(_series(100, 300, 200))
    assert movement is not None
    assert movement.opened_on == date(2024, 6, 8)
    assert movement.closed_on == date(2024, 6, 10)
    assert movement.entries == 3


def test_a_movement_is_read_in_date_order_however_it_arrives() -> None:
    scrambled = list(reversed(_series(100, 300, 200)))
    movement = moved(scrambled)
    assert movement is not None
    assert (movement.opened, movement.closed) == (100, 200)


def test_a_movement_says_how_far_to_trust_itself() -> None:
    movement = moved(_series(1, 1, 1))
    assert movement is not None
    assert movement.confidence is PriceConfidence.UNTRADED


def test_a_price_that_started_at_nothing_reports_no_share() -> None:
    movement = moved(_series(0, 500))
    assert movement is not None
    assert movement.share == 0.0


def test_an_item_with_no_snapshots_never_moved() -> None:
    assert moved([]) is None
