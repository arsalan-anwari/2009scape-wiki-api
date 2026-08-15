"""Turn the strings the game's config files hold into the values the model takes."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.sources.errors import MalformedSourceValue, UnknownSourceField

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

GROUP_SEPARATOR: Final = "-"
VALUE_SEPARATOR: Final = ","
GROUP_OPEN: Final = "{"
GROUP_CLOSE: Final = "}"
TRUE_WORDS: Final = frozenset({"true", "yes", "1"})
FALSE_WORDS: Final = frozenset({"false", "no", "0"})
ABSENT_WORD: Final = "null"
ZERO_WORDS: Final = frozenset({"0", "0.0", "-0"})
SKILL_KEY: Final = "skill"
LEVEL_KEY: Final = "level"


class SkipReason(StrEnum):
    """Why a source row did not become a fact."""

    UNKNOWN_TARGET = "unknown_target"
    UNKNOWN_SUBJECT = "unknown_subject"
    OVERRIDDEN = "overridden"
    NO_CHANCE = "no_chance"
    NO_DROP = "no_drop"
    RESERVED_SLOT = "reserved_slot"
    ALREADY_STATED = "already_stated"
    NO_PLACE = "no_place"
    UNNAMED = "unnamed"


class Skipped(BaseModel):
    """One row a source held and the artifact does not."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    reason: SkipReason
    detail: str = ""


def present(value: Any) -> bool:
    """Say whether a source value carries anything at all."""
    if value is None:
        return False
    if not isinstance(value, str):
        return True
    return bool(value.strip()) and value.strip() != ABSENT_WORD


def text(value: Any) -> str | None:
    """Read a source value as text, with an empty one meaning absent."""
    if not present(value):
        return None
    return str(value).strip()


def whole(value: Any, source: str, record: str, field: str) -> int | None:
    """Read a source value as a whole number, with an empty one meaning absent."""
    if not present(value):
        return None
    try:
        return int(str(value).strip())
    except ValueError as error:
        raise MalformedSourceValue(source, record, field, f"{value!r}") from error


def numbers(value: Any, source: str, record: str, field: str) -> tuple[int, ...]:
    """Read a comma-separated run of whole numbers."""
    if not present(value):
        return ()
    parts = [part.strip() for part in str(value).split(VALUE_SEPARATOR)]
    try:
        return tuple(int(part) for part in parts if part)
    except ValueError as error:
        raise MalformedSourceValue(source, record, field, f"{value!r}") from error


def groups(
    value: Any, source: str, record: str, field: str, width: int
) -> tuple[tuple[int, ...], ...]:
    """Read the braced runs the packed source fields use, checking each one's width."""
    if not present(value):
        return ()
    packed: list[tuple[int, ...]] = []
    for part in str(value).split(GROUP_SEPARATOR):
        cleaned = part.strip()
        if not cleaned:
            continue
        if not cleaned.startswith(GROUP_OPEN) or not cleaned.endswith(GROUP_CLOSE):
            raise MalformedSourceValue(source, record, field, f"{cleaned!r}")
        read = numbers(cleaned[1:-1], source, record, field)
        if len(read) != width:
            raise MalformedSourceValue(
                source, record, field, f"{cleaned!r} is not {width} numbers"
            )
        packed.append(read)
    return tuple(packed)


def requirements(
    value: Any, source: str, record: str
) -> tuple[dict[str, int], ...] | None:
    """Read the packed skill requirements an item carries."""
    read = groups(value, source, record, "requirements", 2)
    if not read:
        return None
    return tuple({SKILL_KEY: skill, LEVEL_KEY: level} for skill, level in read)


def defaulted(value: Any) -> bool:
    """Say whether a value is the zero a writer left behind rather than a fact."""
    if isinstance(value, bool):
        return value is False
    if isinstance(value, int | float):
        return value == 0
    return isinstance(value, str) and value.strip() in ZERO_WORDS


def attributes(
    record: Mapping[str, Any],
    *,
    source: str,
    identity: str,
    spine: Iterable[str],
    ignored: Iterable[str],
    declared: Iterable[str],
    listed: Iterable[str] = (),
    zero_is_absent: Iterable[str] = (),
    renamed: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Keep the fields the model declares, drop the empty ones, refuse the unknown."""
    held = set(spine)
    skipped = set(ignored)
    known = set(declared)
    runs = set(listed)
    defaults = set(zero_is_absent)
    lands_as = dict(renamed or {})
    kept: dict[str, Any] = {}
    for field, value in record.items():
        if field in held or field in skipped:
            continue
        under = lands_as.get(field, field)
        if under not in known:
            raise UnknownSourceField(source, field, identity)
        if not present(value):
            continue
        if field in defaults and defaulted(value):
            continue
        kept[under] = (
            list(numbers(value, source, identity, field)) if field in runs else value
        )
    return kept


def flag(value: Any) -> bool | None:
    """Read a source value as true or false, however the file spelled it."""
    if not present(value):
        return None
    if isinstance(value, bool):
        return value
    word = str(value).strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


# test cases


def test_an_empty_value_means_absent_rather_than_zero() -> None:
    assert text("") is None
    assert text("   ") is None
    assert text(None) is None
    assert whole("", "x", "1", "f") is None
    assert numbers("", "x", "1", "f") == ()
    assert not present("")
    assert present("0")


def test_a_zero_is_told_apart_from_a_number_somebody_meant() -> None:
    assert defaulted("0") is True
    assert defaulted(0) is True
    assert defaulted("0.0") is True
    assert defaulted("70") is False
    assert defaulted("") is False


def test_a_field_whose_zero_is_a_default_is_dropped_only_where_it_is_named() -> None:
    kept = attributes(
        {"ticket": "0", "price": "0"},
        source="items.json",
        identity="1",
        spine=(),
        ignored=(),
        declared=("ticket", "price"),
        zero_is_absent=("ticket",),
    )
    assert kept == {"price": "0"}


def test_the_word_null_means_absent_the_way_the_game_reads_it() -> None:
    assert not present("null")
    assert text("null") is None
    assert whole("null", "x", "1", "f") is None
    assert flag("null") is None
    assert present("nullify")


def test_numbers_arrive_as_numbers() -> None:
    assert whole("4", "x", "1", "f") == 4
    assert numbers("390,390,381", "x", "1", "f") == (390, 390, 381)


def test_a_packed_group_is_read_at_the_width_it_declares() -> None:
    assert groups("{1,2,3}-{4,5,6}-", "x", "1", "stock", 3) == ((1, 2, 3), (4, 5, 6))


def test_a_group_of_the_wrong_width_is_refused() -> None:
    import pytest

    with pytest.raises(MalformedSourceValue):
        groups("{1,2}", "shops.json", "1", "stock", 3)


def test_a_group_without_its_braces_is_refused() -> None:
    import pytest

    with pytest.raises(MalformedSourceValue):
        groups("1,2,3", "shops.json", "1", "stock", 3)


def test_a_value_that_is_not_a_number_is_refused() -> None:
    import pytest

    with pytest.raises(MalformedSourceValue):
        whole("soon", "item_configs.json", "4587", "attack_speed")
    with pytest.raises(MalformedSourceValue):
        numbers("1,two", "item_configs.json", "4587", "attack_anims")


def test_requirements_become_the_shape_the_model_declares() -> None:
    assert requirements("{0,60}", "item_configs.json", "4587") == (
        {"skill": 0, "level": 60},
    )
    assert requirements("{1,20}-{4,20}", "item_configs.json", "1") == (
        {"skill": 1, "level": 20},
        {"skill": 4, "level": 20},
    )
    assert requirements("", "item_configs.json", "1") is None


def test_a_flag_is_read_however_the_file_spelled_it() -> None:
    assert flag("true") is True
    assert flag("True") is True
    assert flag(True) is True
    assert flag("false") is False
    assert flag("") is None
    assert flag("perhaps") is None


def test_attributes_keep_what_is_declared_and_drop_what_is_empty() -> None:
    kept = attributes(
        {"id": "1", "name": "Man", "weight": "1.8", "examine": "", "durability": None},
        source="item_configs.json",
        identity="1",
        spine=("id", "name", "examine"),
        ignored=("durability",),
        declared=("weight",),
    )
    assert kept == {"weight": "1.8"}


def test_a_run_of_numbers_is_split_before_the_model_sees_it() -> None:
    kept = attributes(
        {"attack_anims": "390,381"},
        source="item_configs.json",
        identity="4587",
        spine=(),
        ignored=(),
        declared=("attack_anims",),
        listed=("attack_anims",),
    )
    assert kept == {"attack_anims": [390, 381]}


def test_a_field_nobody_declared_stops_the_build() -> None:
    import pytest

    with pytest.raises(UnknownSourceField) as caught:
        attributes(
            {"sparkle": "yes"},
            source="item_configs.json",
            identity="4587",
            spine=(),
            ignored=(),
            declared=("weight",),
        )
    assert "sparkle" in str(caught.value)


def test_a_skipped_row_records_why_it_was_skipped() -> None:
    skipped = Skipped(
        source="drop_tables.json", reason=SkipReason.UNKNOWN_SUBJECT, detail="npc:2124"
    )
    assert skipped.reason is SkipReason.UNKNOWN_SUBJECT
    assert skipped.detail == "npc:2124"
