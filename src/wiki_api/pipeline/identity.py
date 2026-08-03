"""Give the things the sources do not number an id that survives a rebuild."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.identity import EntityType

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

ALLOCATION_SCHEMA: Final = 1
FIRST_ID: Final = 1


class DuplicateAllocation(ValueError):
    """Two natural keys were given one number."""

    def __init__(self, entity_type: EntityType, number: int) -> None:
        super().__init__(f"two {entity_type.value} keys are both allocated {number}")
        self.entity_type = entity_type
        self.number = number


class IdentityAllocation(BaseModel):
    """The numbers already handed out to one type's natural keys."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    schema_version: int = Field(default=ALLOCATION_SCHEMA, alias="schema")
    type: EntityType
    ids: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _one_number_each(self) -> Self:
        seen: set[int] = set()
        for number in self.ids.values():
            if number in seen:
                raise DuplicateAllocation(self.type, number)
            seen.add(number)
        return self

    def id_of(self, source_key: str) -> int | None:
        return self.ids.get(source_key)

    def extended_with(self, source_keys: Iterable[str]) -> IdentityAllocation:
        """A copy that has numbered anything it had not seen before, in the order
        the source lists it.
        """
        given = dict(self.ids)
        next_id = max(given.values(), default=FIRST_ID - 1) + 1
        for source_key in source_keys:
            if source_key in given:
                continue
            given[source_key] = next_id
            next_id += 1
        return self.model_copy(update={"ids": given})

    @property
    def added(self) -> int:
        return len(self.ids)


def allocation_path(directory: Path, entity_type: EntityType) -> Path:
    """Where one type's allocations are written down."""
    return directory / f"{entity_type.value}.json"


def read_allocation(directory: Path, entity_type: EntityType) -> IdentityAllocation:
    """Read the allocations for one type, or an empty set if none were written yet."""
    path = allocation_path(directory, entity_type)
    if not path.is_file():
        return IdentityAllocation(type=entity_type)
    return IdentityAllocation.model_validate_json(path.read_text(encoding="utf-8"))


def write_allocation(directory: Path, allocation: IdentityAllocation) -> Path:
    """Write the allocations out, sorted by number so a review reads as a history."""
    directory.mkdir(parents=True, exist_ok=True)
    path = allocation_path(directory, allocation.type)
    ordered = dict(sorted(allocation.ids.items(), key=lambda pair: pair[1]))
    payload = {
        "schema": allocation.schema_version,
        "type": allocation.type.value,
        "ids": ordered,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


# test cases


def test_a_key_keeps_the_number_it_was_first_given() -> None:
    first = IdentityAllocation(type=EntityType.QUEST).extended_with(["A", "B"])
    second = first.extended_with(["B", "A", "C"])
    assert first.id_of("A") == second.id_of("A")
    assert first.id_of("B") == second.id_of("B")
    assert second.id_of("C") == 3


def test_numbering_starts_at_one_and_never_reuses() -> None:
    allocation = IdentityAllocation(type=EntityType.QUEST).extended_with(["A", "B"])
    assert allocation.ids == {"A": 1, "B": 2}
    shortened = IdentityAllocation(type=EntityType.QUEST, ids={"A": 1, "B": 2})
    assert shortened.extended_with(["C"]).id_of("C") == 3


def test_an_order_the_source_changed_does_not_move_an_existing_number() -> None:
    allocation = IdentityAllocation(type=EntityType.QUEST, ids={"A": 1, "B": 2})
    assert allocation.extended_with(["B", "A"]).ids == {"A": 1, "B": 2}


def test_a_key_nobody_numbered_reads_as_nothing() -> None:
    assert IdentityAllocation(type=EntityType.QUEST).id_of("A") is None


def test_allocations_round_trip_through_the_file(tmp_path: Path) -> None:
    allocation = IdentityAllocation(type=EntityType.QUEST).extended_with(["A", "B"])
    write_allocation(tmp_path, allocation)
    assert read_allocation(tmp_path, EntityType.QUEST) == allocation


def test_reading_before_anything_was_allocated_gives_an_empty_set(
    tmp_path: Path,
) -> None:
    allocation = read_allocation(tmp_path, EntityType.QUEST)
    assert allocation.ids == {}
    assert allocation.type is EntityType.QUEST


def test_the_written_file_reads_in_the_order_the_numbers_were_given(
    tmp_path: Path,
) -> None:
    write_allocation(
        tmp_path, IdentityAllocation(type=EntityType.QUEST, ids={"B": 2, "A": 1})
    )
    written = json.loads(
        allocation_path(tmp_path, EntityType.QUEST).read_text(encoding="utf-8")
    )
    assert list(written["ids"]) == ["A", "B"]


def test_two_keys_sharing_a_number_are_refused() -> None:
    import pytest

    with pytest.raises(ValueError):
        IdentityAllocation(type=EntityType.QUEST, ids={"A": 1, "B": 1})
