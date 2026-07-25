from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Sequence

NOTHING_ITEM_ID: Final = 0


class DropRoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: int = Field(ge=0)
    weight: float = Field(gt=0.0)
    min_amount: int = Field(ge=1)
    max_amount: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_amounts(self) -> Self:
        if self.max_amount < self.min_amount:
            raise ValueError("max_amount must not be below min_amount")
        return self

    @property
    def is_reward(self) -> bool:
        return self.item_id != NOTHING_ITEM_ID


def drop_denominator(rolls: Sequence[DropRoll]) -> float:
    if not rolls:
        raise ValueError("a drop table needs at least one roll")
    return sum(roll.weight for roll in rolls)


def rewarding_rolls(rolls: Sequence[DropRoll]) -> tuple[DropRoll, ...]:
    return tuple(roll for roll in rolls if roll.is_reward)


def test_the_denominator_includes_the_nothing_roll() -> None:
    rolls = [
        DropRoll(item_id=7980, weight=1.0, min_amount=1, max_amount=1),
        DropRoll(item_id=NOTHING_ITEM_ID, weight=127.0, min_amount=1, max_amount=1),
    ]
    assert drop_denominator(rolls) == 128.0
    rewards = rewarding_rolls(rolls)
    assert len(rewards) == 1
    assert rewards[0].weight / drop_denominator(rolls) == 1 / 128


def test_weights_that_do_not_sum_to_a_round_number_are_kept_exact() -> None:
    rolls = [
        DropRoll(item_id=1369, weight=50.0, min_amount=1, max_amount=1),
        DropRoll(item_id=1315, weight=970.20404, min_amount=1, max_amount=1),
    ]
    assert drop_denominator(rolls) == 1020.20404


def test_an_empty_table_has_no_denominator() -> None:
    import pytest

    with pytest.raises(ValueError):
        drop_denominator([])


def test_a_roll_cannot_have_an_inverted_amount_range() -> None:
    import pytest

    with pytest.raises(ValueError):
        DropRoll(item_id=995, weight=1.0, min_amount=100, max_amount=1)


def test_a_roll_needs_a_positive_weight() -> None:
    import pytest

    with pytest.raises(ValueError):
        DropRoll(item_id=995, weight=0.0, min_amount=1, max_amount=1)
