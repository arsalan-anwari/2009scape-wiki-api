"""Paging, because nothing this API returns is unbounded."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

DEFAULT_PAGE_SIZE: Final = 50
MAX_PAGE_SIZE: Final = 200


class SortOrder(StrEnum):
    """How a listing is sorted: alphabetically by name, or by id."""

    NAME = "name"
    ID = "id"


class Page[T](BaseModel):
    """One page of results, and enough about the whole to ask for the next.

    `total` counts everything that matched, not what is in `items`. `next_offset` is
    the offset to ask for next, and is null once you have reached the end.
    """

    model_config = ConfigDict(frozen=True)

    items: tuple[T, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_PAGE_SIZE)
    offset: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if len(self.items) > self.limit:
            raise ValueError("a page cannot hold more items than its limit")
        if len(self.items) > self.total:
            raise ValueError("a page cannot hold more items than the total")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_offset(self) -> int | None:
        if not self.has_more:
            return None
        return self.offset + len(self.items)


# test cases


def test_a_page_reports_whether_more_results_follow() -> None:
    page = Page[int](items=(1, 2), total=5, limit=2, offset=0)
    assert page.has_more is True
    assert page.next_offset == 2


def test_the_last_page_has_no_next_offset() -> None:
    page = Page[int](items=(5,), total=5, limit=2, offset=4)
    assert page.has_more is False
    assert page.next_offset is None


def test_an_empty_page_is_valid() -> None:
    page = Page[str](items=(), total=0, limit=DEFAULT_PAGE_SIZE, offset=0)
    assert page.items == ()
    assert page.has_more is False
    assert page.next_offset is None


def test_a_page_cannot_exceed_its_own_limit_or_total() -> None:
    import pytest

    with pytest.raises(ValueError):
        Page[int](items=(1, 2, 3), total=10, limit=2, offset=0)
    with pytest.raises(ValueError):
        Page[int](items=(1, 2, 3), total=2, limit=10, offset=0)


def test_page_sizes_are_bounded() -> None:
    import pytest

    with pytest.raises(ValueError):
        Page[int](items=(), total=0, limit=MAX_PAGE_SIZE + 1, offset=0)
    with pytest.raises(ValueError):
        Page[int](items=(), total=0, limit=0, offset=0)


def test_pages_keep_the_item_type() -> None:
    page = Page[str].model_validate(
        {"items": ["a", "b"], "total": 2, "limit": 10, "offset": 0}
    )
    assert page.items == ("a", "b")


def test_a_reader_is_told_where_the_next_page_starts_without_computing_it() -> None:
    rendered = Page[int](items=(1, 2), total=5, limit=2, offset=0).model_dump(
        mode="json"
    )
    assert rendered["has_more"] is True
    assert rendered["next_offset"] == 2


def test_the_end_of_a_listing_says_so_on_the_wire() -> None:
    rendered = Page[int](items=(5,), total=5, limit=2, offset=4).model_dump(mode="json")
    assert rendered["has_more"] is False
    assert rendered["next_offset"] is None


def test_a_page_survives_a_round_trip_through_its_own_rendering() -> None:
    page = Page[int](items=(1, 2), total=5, limit=2, offset=0)
    assert Page[int].model_validate_json(page.model_dump_json()) == page
