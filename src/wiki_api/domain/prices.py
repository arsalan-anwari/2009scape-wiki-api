from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence


class PricePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=0)
    snapshot_date: date
    value: int = Field(ge=0)


def latest_price(points: Sequence[PricePoint]) -> PricePoint | None:
    if not points:
        return None
    return max(points, key=lambda point: point.snapshot_date)


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
