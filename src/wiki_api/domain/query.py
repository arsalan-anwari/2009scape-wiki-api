"""Say which declared values a caller may compare, and hold the comparison they asked
for.

A path addresses a declared value, either a whole attribute or one part of a packed one,
and is only ever built from the registry.
"""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.attributes import (
    ATTRIBUTE_SPECS,
    PATH_SEPARATOR,
    AttributeSpec,
)
from wiki_api.domain.identity import EntityType
from wiki_api.domain.vocabulary import AttributeFormat, GameEnum

COMPARABLE_FORMATS: Final = frozenset(
    {
        AttributeFormat.INT,
        AttributeFormat.FLOAT,
        AttributeFormat.GP,
        AttributeFormat.RATE,
    }
)

PATH_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$")

_WORD_BREAK: Final = re.compile(r"[^a-z0-9]+")


class Comparison(GameEnum):
    """How a stored number is measured against the one a caller gave."""

    AT_LEAST = "at_least"
    MORE_THAN = "more_than"
    AT_MOST = "at_most"
    LESS_THAN = "less_than"
    EQUALS = "equals"


class Comparable(BaseModel):
    """One declared value a caller may compare, and how to address it."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(pattern=PATH_PATTERN.pattern)
    spec: AttributeSpec


class Condition(BaseModel):
    """One comparison to hold a stored value against."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(pattern=PATH_PATTERN.pattern)
    compare: Comparison
    value: float


class Ordering(BaseModel):
    """Which declared value to sort by, and which way round."""

    model_config = ConfigDict(frozen=True)

    path: str = Field(pattern=PATH_PATTERN.pattern)
    descending: bool = False


def comparable_of(entity_type: EntityType) -> tuple[Comparable, ...]:
    """Every declared value of one type that holds a number worth comparing."""
    return tuple(
        Comparable(path=path, spec=spec)
        for declared in ATTRIBUTE_SPECS[entity_type]
        if declared.display
        for path, spec in declared.paths()
        if spec.format in COMPARABLE_FORMATS
    )


def understood(entity_type: EntityType, wanted: str) -> Comparable | None:
    """Match a caller's words to one comparable value, or to nothing at all.

    A word that matches no declared value is never guessed at, because the second best
    match answers a question nobody asked.
    """
    asked = _folded(wanted)
    if not asked:
        return None
    offered = comparable_of(entity_type)
    for candidate in offered:
        if asked in _spellings(candidate):
            return candidate
    return None


def _spellings(candidate: Comparable) -> frozenset[str]:
    return frozenset(
        {
            _folded(candidate.path),
            _folded(candidate.path.rpartition(PATH_SEPARATOR)[2]),
            _folded(candidate.spec.label),
        }
    )


def _folded(words: str) -> str:
    return _WORD_BREAK.sub(" ", words.strip().lower()).strip()


# test cases


def test_a_plain_number_is_comparable_and_a_word_is_not() -> None:
    paths = {one.path for one in comparable_of(EntityType.ITEM)}
    assert "ge_buy_limit" in paths
    assert "tradeable" not in paths
    assert "equipment_slot" not in paths


def test_a_part_of_a_packed_value_is_comparable_on_its_own() -> None:
    paths = {one.path for one in comparable_of(EntityType.ITEM)}
    assert "bonuses.strength" in paths
    assert "bonuses" not in paths


def test_a_type_whose_values_are_all_words_offers_nothing_to_compare() -> None:
    assert comparable_of(EntityType.SHOP) == ()
    assert comparable_of(EntityType.QUEST)


def test_a_value_is_found_by_its_label_however_it_is_typed() -> None:
    found = understood(EntityType.ITEM, "  Strength BONUS ")
    assert found is not None
    assert found.path == "bonuses.strength"


def test_a_value_is_found_by_the_name_the_registry_gives_it() -> None:
    for wanted in ("bonuses.strength", "strength"):
        found = understood(EntityType.ITEM, wanted)
        assert found is not None
        assert found.path == "bonuses.strength"


def test_words_that_match_nothing_are_answered_with_nothing() -> None:
    assert understood(EntityType.ITEM, "how shiny it is") is None
    assert understood(EntityType.ITEM, "  ") is None


def test_a_value_of_another_type_is_not_offered() -> None:
    assert understood(EntityType.QUEST, "bonuses.strength") is None
    assert understood(EntityType.NPC, "combat level") is not None


def test_a_path_a_registry_would_never_produce_is_refused() -> None:
    import pytest

    for bad in ("$.value", "a.b.c", "Attack", "", "x'; drop table entity"):
        with pytest.raises(ValueError):
            Ordering(path=bad)


def test_a_comparison_names_itself_on_the_wire() -> None:
    condition = Condition(path="heals", compare=Comparison.MORE_THAN, value=10)
    assert condition.model_dump(mode="json")["compare"] == "more_than"


def test_an_ordering_reads_upwards_unless_it_says_otherwise() -> None:
    assert Ordering(path="heals").descending is False
