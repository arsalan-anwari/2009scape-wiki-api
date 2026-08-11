"""Render a declared value into the words a reader sees, falling back to the value
itself on a format this module does not know.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.vocabulary import AttributeFormat

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import JsonValue

    from wiki_api.core import AttributeValue

ABSENT = "unknown"
YES = "yes"
NO = "no"
MOST_PARTS = 8
POINTED_AT = "label"


def rendered(value: AttributeValue) -> str:
    """Render one declared value as words."""
    said = _said(value.value, value.format)
    if value.unit is None:
        return said
    return f"{said} {value.unit.value}"


def labelled(values: Sequence[AttributeValue]) -> dict[str, str]:
    """Render several declared values, each under the name the registry gives it."""
    return {value.label: rendered(value) for value in values}


def _said(value: JsonValue, shape: AttributeFormat) -> str:
    if value is None:
        return ABSENT
    if shape is AttributeFormat.RATE:
        return _odds(value)
    if shape is AttributeFormat.REF:
        return _pointed(value)
    return _plain(value)


def _pointed(value: JsonValue) -> str:
    if isinstance(value, dict):
        named = value.get(POINTED_AT)
        if isinstance(named, str):
            return named
    return _plain(value)


def _odds(value: JsonValue) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return _plain(value)
    return f"1/{round(1 / value)}"


def _plain(value: JsonValue) -> str:
    if isinstance(value, bool):
        return YES if value else NO
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return ", ".join(_plain(part) for part in value[:MOST_PARTS])
    if isinstance(value, dict):
        return ", ".join(
            f"{under} {_plain(part)}"
            for under, part in list(value.items())[:MOST_PARTS]
        )
    return ABSENT


# test cases


def _value(
    raw: JsonValue, shape: AttributeFormat, unit: object = None
) -> AttributeValue:
    from wiki_api.core import AttributeValue as Declared
    from wiki_api.domain.vocabulary import AttributeGroup, Unit

    return Declared(
        key="declared",
        value=raw,
        label="Declared",
        group=AttributeGroup.OVERVIEW,
        order=10,
        format=shape,
        unit=unit if isinstance(unit, Unit) else None,
    )


def test_a_likelihood_reads_the_way_a_player_would_say_it() -> None:
    assert rendered(_value(1 / 128, AttributeFormat.RATE)) == "1/128"


def test_a_likelihood_nobody_could_divide_falls_back_to_the_number() -> None:
    assert rendered(_value(0.0, AttributeFormat.RATE)) == "0"


def test_a_yes_or_no_never_reaches_a_reader_as_a_python_word() -> None:
    assert rendered(_value(True, AttributeFormat.BOOL)) == YES
    assert rendered(_value(False, AttributeFormat.BOOL)) == NO


def test_a_measured_value_carries_what_it_was_measured_in() -> None:
    from wiki_api.domain.vocabulary import Unit

    assert rendered(_value(3, AttributeFormat.INT, Unit.TILES)) == "3 tiles"


def test_a_format_this_surface_has_never_heard_of_still_says_something() -> None:
    unknown = AttributeFormat("text")
    assert rendered(_value("Burthorpe", unknown)) == "Burthorpe"


def test_a_value_made_of_parts_is_said_as_its_parts() -> None:
    assert rendered(_value({"x": 2273, "y": 4698}, AttributeFormat.COORD)) == (
        "x 2273, y 4698"
    )


def test_a_run_of_parts_is_cut_before_it_floods_a_reader() -> None:
    many: JsonValue = list(range(MOST_PARTS * 2))
    said = rendered(_value(many, AttributeFormat.IDS))
    assert said.count(",") == MOST_PARTS - 1


def test_nothing_recorded_says_so_rather_than_saying_nothing() -> None:
    assert rendered(_value(None, AttributeFormat.INT)) == ABSENT


def test_a_gap_inside_a_value_says_so_rather_than_saying_none() -> None:
    said = rendered(_value({"x": 2273, "y": None}, AttributeFormat.COORD))
    assert said == f"x 2273, y {ABSENT}"


def test_several_values_come_back_under_the_names_they_were_given() -> None:
    assert labelled([_value(7, AttributeFormat.INT)]) == {"Declared": "7"}


def test_a_pointer_is_said_as_the_thing_it_points_at() -> None:
    pointer: JsonValue = {
        "type": "item",
        "id": 303,
        "slug": "small-fishing-net",
        POINTED_AT: "Small fishing net",
    }
    assert rendered(_value(pointer, AttributeFormat.REF)) == "Small fishing net"


def test_a_pointer_nobody_resolved_still_says_where_it_pointed() -> None:
    pointer: JsonValue = {"type": "item", "id": 303}
    assert rendered(_value(pointer, AttributeFormat.REF)) == "type item, id 303"
