"""Turn the weights in a drop table into rates a reader can understand."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Sequence

NOTHING_ITEM_ID: Final = 0


class DropRoll(BaseModel):
    """One line of a drop table, before it becomes an edge."""

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
    """The total weight of a table, which is what every roll is out of."""
    if not rolls:
        raise ValueError("a drop table needs at least one roll")
    return sum(roll.weight for roll in rolls)


def rewarding_rolls(rolls: Sequence[DropRoll]) -> tuple[DropRoll, ...]:
    """The rolls that actually give something, dropping the filler that pads a table."""
    return tuple(roll for roll in rolls if roll.is_reward)


def drop_order_key(weight: float, denominator: float) -> int:
    """A sort key that puts the common drops before the rare ones."""
    if weight <= 0.0 or denominator <= 0.0:
        raise ValueError("a drop needs a positive weight and denominator")
    return round(denominator / weight)


# test cases


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


def test_the_order_key_ranks_a_drop_by_rarity_in_both_directions() -> None:
    common = drop_order_key(64.0, 128.0)
    rare = drop_order_key(1.0, 128.0)
    assert common == 2
    assert rare == 128
    assert common < rare


def test_the_order_key_is_comparable_across_two_different_tables() -> None:
    kbd_heads = drop_order_key(1.0, 128.0)
    kbd_main = drop_order_key(50.0, 1020.20404)
    assert kbd_main == 20
    assert kbd_main < kbd_heads


def test_an_impossible_drop_has_no_order_key() -> None:
    import pytest

    for weight, denominator in ((0.0, 128.0), (1.0, 0.0)):
        with pytest.raises(ValueError):
            drop_order_key(weight, denominator)
