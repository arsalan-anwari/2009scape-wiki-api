"""Read the arguments a class hands its base class, for the facts only code states."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.enums.gates import QuestGates

if TYPE_CHECKING:
    from collections.abc import Iterator

CONSTANT: Final = re.compile(r"^[A-Z][A-Z0-9_]*$")


class BaseCall(BaseModel):
    """One call to a base class, with the enum constant it names and its numbers."""

    model_config = ConfigDict(frozen=True)

    constant: str = Field(min_length=1)
    numbers: tuple[int, ...] = ()
    requires: QuestGates | None = None

    def number(self, position: int) -> int | None:
        """The argument at a position, counting the enum constant as position zero."""
        index = position - 1
        if index < 0 or index >= len(self.numbers):
            return None
        return self.numbers[index]


def read_base_calls(source: str, base: str, qualifier: str) -> tuple[BaseCall, ...]:
    """Read every `Base(Qualifier.CONSTANT, 1, 2, ...)` and `super(...)` the file makes.

    `qualifier` is the enum the first argument is written against, so a call naming
    anything else is left alone.
    """
    return tuple(_calls(source, base, qualifier))


def _calls(source: str, base: str, qualifier: str) -> Iterator[BaseCall]:
    opener = re.compile(rf"\b(?:{re.escape(base)}|super)\s*\(")
    prefix = f"{qualifier}."
    for match in opener.finditer(source):
        arguments = _arguments(source, match.end())
        if arguments is None or not arguments[0].startswith(prefix):
            continue
        constant = arguments[0].removeprefix(prefix)
        if not CONSTANT.match(constant):
            continue
        yield BaseCall(constant=constant, numbers=tuple(_numbers(arguments[1:])))


def _arguments(source: str, start: int) -> tuple[str, ...] | None:
    depth = 1
    at = start
    parts: list[str] = []
    current: list[str] = []
    while at < len(source) and depth:
        character = source[at]
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
            if not depth:
                break
        if depth == 1 and character == ",":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        at += 1
    if depth:
        return None
    parts.append("".join(current).strip())
    return tuple(parts) if parts[0] else None


def _numbers(arguments: tuple[str, ...]) -> Iterator[int]:
    for argument in arguments:
        try:
            yield int(argument)
        except ValueError:
            return


# test cases

KOTLIN: Final = "class DeathPlateau : Quest(Quests.DEATH_PLATEAU,44, 43, 1, 314, 0) {"
JAVA: Final = """
public class GoblinDiplomacy extends Quest {
    public GoblinDiplomacy() {
        super(Quests.GOBLIN_DIPLOMACY, 20, 19, 5);
    }
}
"""


def test_a_kotlin_class_hands_its_numbers_to_its_base() -> None:
    read = read_base_calls(KOTLIN, "Quest", "Quests")
    assert len(read) == 1
    assert read[0].constant == "DEATH_PLATEAU"
    assert read[0].numbers == (44, 43, 1, 314, 0)
    assert read[0].number(3) == 1


def test_a_java_class_hands_the_same_numbers_through_super() -> None:
    read = read_base_calls(JAVA, "Quest", "Quests")
    assert read[0].constant == "GOBLIN_DIPLOMACY"
    assert read[0].number(3) == 5


def test_a_position_beyond_what_the_call_states_is_absent() -> None:
    read = read_base_calls(JAVA, "Quest", "Quests")
    assert read[0].number(9) is None
    assert read[0].number(0) is None


def test_a_call_naming_another_enum_is_left_alone() -> None:
    assert read_base_calls("class X : Quest(Tasks.BATS, 1)", "Quest", "Quests") == ()


def test_a_call_stops_reading_at_the_first_argument_that_is_not_a_number() -> None:
    read = read_base_calls(
        "class X : Quest(Quests.A_QUEST, 1, 2, 3, someName, 9)", "Quest", "Quests"
    )
    assert read[0].numbers == (1, 2, 3)


def test_a_nested_call_does_not_end_the_argument_list() -> None:
    read = read_base_calls(
        "class X : Quest(Quests.A_QUEST, index(1, 2), 3)", "Quest", "Quests"
    )
    assert read[0].constant == "A_QUEST"
    assert read[0].numbers == ()


def test_an_unclosed_call_is_read_as_nothing() -> None:
    assert read_base_calls("class X : Quest(Quests.A_QUEST, 1", "Quest", "Quests") == ()
