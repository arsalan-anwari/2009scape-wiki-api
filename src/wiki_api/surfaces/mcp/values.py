"""Render a declared value into the words a reader sees, falling back to the value
itself on a format this module does not know.

A value whose parts the registry declares is written in full under their labels; a
run of parts nothing declares is cut, and says how many it left out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.vocabulary import AttributeFormat

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from pydantic import JsonValue

    from wiki_api.core import AttributeValue
    from wiki_api.domain.attributes import AttributeSpec

ABSENT = "unknown"
YES = "yes"
NO = "no"
MOST_PARTS = 8
POINTED_AT = "label"
LEFT_OUT = "and {count} more"
ALONGSIDE = ", "
BESIDE = "; "


def rendered(value: AttributeValue, parts: Sequence[AttributeSpec] = ()) -> str:
    """Render one declared value as words, naming its parts where it declares any."""
    said = _said(value.value, value.format, parts)
    if value.unit is None:
        return said
    return f"{said} {value.unit.value}"


def labelled(
    values: Sequence[AttributeValue], declared: Sequence[AttributeSpec] = ()
) -> dict[str, str]:
    """Render several declared values, each under the name the registry gives it.

    A value the registry calls technical is left out: a coordinate, a region number or
    an internal identity is what a map is drawn from, not something a person asked to
    be told, and every one of them costs a reader words it would rather spend on the
    answer.
    """
    parts = _declared_parts(declared)
    return {
        value.label: rendered(value, parts.get(value.key, ()))
        for value in values
        if not value.technical
    }


def _declared_parts(
    declared: Sequence[AttributeSpec],
) -> Mapping[str, Sequence[AttributeSpec]]:
    return {spec.key: spec.fields for spec in declared if spec.fields}


def _said(
    value: JsonValue, shape: AttributeFormat, parts: Sequence[AttributeSpec] = ()
) -> str:
    if value is None:
        return ABSENT
    if shape is AttributeFormat.RATE:
        return _odds(value)
    if shape is AttributeFormat.REF:
        return _pointed(value)
    if parts and isinstance(value, list):
        return _run_of_parts(value, parts)
    if parts and isinstance(value, dict):
        return _named_parts(value, parts)
    return _plain(value)


def _run_of_parts(values: Sequence[JsonValue], parts: Sequence[AttributeSpec]) -> str:
    """Say a run of things whose parts the registry declares, values alone."""
    return _cut([_unnamed_parts(one, parts) for one in values])


def _unnamed_parts(value: JsonValue, parts: Sequence[AttributeSpec]) -> str:
    if not isinstance(value, dict):
        return _plain(value)
    said = " ".join(
        _plain(value[part.key]) for part in parts if value.get(part.key) is not None
    )
    return said[:1].upper() + said[1:] if said else _plain(value)


def _named_parts(value: Mapping[str, JsonValue], parts: Sequence[AttributeSpec]) -> str:
    return ", ".join(
        f"{part.label} {_plain(value[part.key])}" for part in parts if part.key in value
    )


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
        return _cut([_plain(part) for part in value], _between(value))
    if isinstance(value, dict):
        return _cut([f"{under} {_plain(part)}" for under, part in value.items()])
    return ABSENT


def _between(parts: Sequence[JsonValue]) -> str:
    """Keep one entry of a run apart from the next where an entry has commas of its
    own, or two levels of comma read as one list twice as long.
    """
    if any(isinstance(part, dict | list) for part in parts):
        return BESIDE
    return ALONGSIDE


def _cut(said: Sequence[str], between: str = ALONGSIDE) -> str:
    if len(said) <= MOST_PARTS:
        return between.join(said)
    kept = between.join(said[:MOST_PARTS])
    return f"{kept}{between}{LEFT_OUT.format(count=len(said) - MOST_PARTS)}"


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


def test_a_run_of_parts_nothing_declares_is_cut_before_it_floods_a_reader() -> None:
    many: JsonValue = list(range(MOST_PARTS * 2))
    said = rendered(_value(many, AttributeFormat.IDS))
    assert said.startswith("0, 1, 2")
    assert said.endswith(LEFT_OUT.format(count=MOST_PARTS))


def _asked() -> tuple[AttributeValue, tuple[AttributeSpec, ...]]:
    from wiki_api.domain.attributes import ATTRIBUTE_SPECS
    from wiki_api.domain.identity import EntityType

    declared = next(
        spec
        for spec in ATTRIBUTE_SPECS[EntityType.QUEST]
        if spec.format is AttributeFormat.SKILLS and spec.fields
    )
    held: JsonValue = [
        {part.key: value for part, value in zip(declared.fields, one, strict=True)}
        for one in (("magic", 50), ("slayer", 10))
    ]
    return _value(held, AttributeFormat.SKILLS), declared.fields


def test_a_run_of_declared_parts_is_said_as_its_values_alone() -> None:
    """This used to come back as `skill magic, level 50; skill slayer, level 10`,
    ten words to say what four say.
    """
    value, parts = _asked()
    assert rendered(value, parts) == "Magic 50, Slayer 10"


def test_an_entry_shaped_some_other_way_still_says_what_it_holds() -> None:
    _, parts = _asked()
    said = rendered(_value(["anything"], AttributeFormat.SKILLS), parts)
    assert said == "anything"


def test_a_run_of_plain_values_still_reads_as_one_list() -> None:
    assert rendered(_value([1, 2, 3], AttributeFormat.IDS)) == "1, 2, 3"


def test_a_run_that_was_cut_says_how_much_it_left_out() -> None:
    said = rendered(_value(list(range(MOST_PARTS + 3)), AttributeFormat.IDS))
    assert LEFT_OUT.format(count=3) in said


def test_a_run_short_enough_to_write_out_says_nothing_about_leaving_out() -> None:
    said = rendered(_value(list(range(MOST_PARTS)), AttributeFormat.IDS))
    assert "more" not in said


def _packed() -> tuple[AttributeValue, tuple[AttributeSpec, ...]]:
    from wiki_api.domain.attributes import ATTRIBUTE_SPECS
    from wiki_api.domain.identity import EntityType

    packed = next(
        spec
        for spec in ATTRIBUTE_SPECS[EntityType.ITEM]
        if spec.format is AttributeFormat.BONUSES
    )
    held: JsonValue = {part.key: number for number, part in enumerate(packed.fields)}
    return _value(held, AttributeFormat.BONUSES), packed.fields


def test_a_value_whose_parts_are_declared_names_every_one_of_them() -> None:
    value, parts = _packed()
    said = rendered(value, parts)
    for part in parts:
        assert part.label in said


def test_a_declared_part_is_never_cut_for_being_far_down_the_run() -> None:
    """The strength bonus sits eleventh of fifteen, which the cut used to lose in
    silence on every weapon in the game.
    """
    value, parts = _packed()
    last = parts[-1]
    assert f"{last.label} 14" in rendered(value, parts)


def test_a_part_a_record_leaves_out_is_left_out_rather_than_guessed() -> None:
    _, parts = _packed()
    thinner = _value({parts[0].key: 4}, AttributeFormat.BONUSES)
    assert rendered(thinner, parts) == f"{parts[0].label} 4"


def test_the_same_value_without_its_parts_still_says_something() -> None:
    value, _ = _packed()
    assert rendered(value) != ""


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


def test_a_value_that_addresses_the_game_is_never_said_in_words() -> None:
    """A place used to be answered as `x 3108, y 3345, plane 0, Region 12340`, four
    numbers nobody asked for and none of which name anywhere.
    """
    from wiki_api.core import AttributeValue as Declared
    from wiki_api.domain.attributes import ATTRIBUTE_SPECS
    from wiki_api.domain.identity import EntityType

    specs = ATTRIBUTE_SPECS[EntityType.LOCATION]
    addressing = [spec for spec in specs if spec.technical]
    assert {spec.key for spec in addressing} == {"centre", "bounds", "region_id"}
    said = labelled([Declared.of(spec, 1) for spec in specs if spec.display])
    assert not {spec.label for spec in addressing} & set(said)


def test_a_value_that_describes_the_game_is_still_said() -> None:
    from wiki_api.core import AttributeValue as Declared
    from wiki_api.domain.attributes import ATTRIBUTE_SPECS
    from wiki_api.domain.identity import EntityType

    specs = ATTRIBUTE_SPECS[EntityType.LOCATION]
    said = labelled([Declared.of(spec, 1) for spec in specs if spec.display])
    assert "Wilderness level" in said
