"""Read one constant's arguments into plain values, folding the arithmetic away."""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from wiki_api.pipeline.enums.errors import UnreadableConstant
from wiki_api.pipeline.enums.lexer import Token, TokenKind

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type EnumValue = (
    int | float | str | bool | list["EnumValue"] | dict[str, "EnumValue"] | None
)

SYMBOL_KEY: Final = "symbol"
CALL_KEY: Final = "call"
ARGUMENTS_KEY: Final = "arguments"
ARRAY_BUILDERS: Final = frozenset(
    {"arrayOf", "intArrayOf", "doubleArrayOf", "longArrayOf", "listOf", "setOf"}
)
WORD_VALUES: Final[Mapping[str, EnumValue]] = {
    "true": True,
    "false": False,
    "null": None,
}
NUMBER_SUFFIXES: Final = "lLfFdD"
BINARY_LEVELS: Final[tuple[Mapping[str, Callable[[float, float], float]], ...]] = (
    {"|": operator.or_},
    {"^": operator.xor},
    {"&": operator.and_},
    {"<<": operator.lshift, ">>": operator.rshift, ">>>": operator.rshift},
    {"+": operator.add, "-": operator.sub},
    {"*": operator.mul, "/": operator.truediv, "%": operator.mod},
)
BITWISE_MARKS: Final = frozenset({"|", "^", "&", "<<", ">>", ">>>"})


def read_arguments(
    tokens: Sequence[Token], origin: str, constant: str
) -> tuple[EnumValue, ...]:
    """Read the argument list between one constant's brackets."""
    parser = _Parser(tokens, origin, constant)
    if parser.done():
        return ()
    values = [parser.expression()]
    while parser.take_punctuation(","):
        if parser.done():
            break
        values.append(parser.expression())
    if not parser.done():
        raise parser.fail(f"unexpected {parser.peek().value!r}")
    return tuple(values)


def number_of(text: str, origin: str, constant: str) -> int | float:
    """Turn a Java or Kotlin number literal into the number it means."""
    cleaned = text.replace("_", "")
    based = cleaned.lower().startswith(("0x", "0b", "0o"))
    while not based and cleaned and cleaned[-1] in NUMBER_SUFFIXES:
        floating = cleaned[-1] in "fFdD"
        cleaned = cleaned[:-1]
        if floating:
            return _as_float(cleaned, text, origin, constant)
    if not based and any(mark in cleaned for mark in (".", "e", "E")):
        return _as_float(cleaned, text, origin, constant)
    try:
        return int(cleaned, 0)
    except ValueError as error:
        raise UnreadableConstant(origin, constant, f"bad number {text!r}") from error


def _as_float(cleaned: str, text: str, origin: str, constant: str) -> float:
    try:
        return float(cleaned)
    except ValueError as error:
        raise UnreadableConstant(origin, constant, f"bad number {text!r}") from error


class _Parser:
    def __init__(self, tokens: Sequence[Token], origin: str, constant: str) -> None:
        self.tokens = tokens
        self.origin = origin
        self.constant = constant
        self.at = 0

    def done(self) -> bool:
        return self.at >= len(self.tokens)

    def peek(self) -> Token:
        if self.done():
            raise self.fail("the arguments end early")
        return self.tokens[self.at]

    def take(self) -> Token:
        token = self.peek()
        self.at += 1
        return token

    def take_punctuation(self, mark: str) -> bool:
        if not self.done() and self.peek().punctuation(mark):
            self.at += 1
            return True
        return False

    def expect(self, mark: str) -> None:
        if not self.take_punctuation(mark):
            found = "the end" if self.done() else repr(self.peek().value)
            raise self.fail(f"expected {mark!r}, found {found}")

    def fail(self, detail: str) -> UnreadableConstant:
        return UnreadableConstant(self.origin, self.constant, detail)

    def expression(self, level: int = 0) -> EnumValue:
        if level == len(BINARY_LEVELS):
            return self.unary()
        marks = BINARY_LEVELS[level]
        left = self.expression(level + 1)
        while not self.done() and self.peek().value in marks:
            if self.peek().kind is not TokenKind.PUNCTUATION:
                break
            mark = self.take().value
            right = self.expression(level + 1)
            left = self.fold(mark, marks[mark], left, right)
        return left

    def fold(
        self,
        mark: str,
        apply: Callable[[float, float], float],
        left: EnumValue,
        right: EnumValue,
    ) -> EnumValue:
        if not isinstance(left, int | float) or not isinstance(right, int | float):
            raise self.fail(f"{mark!r} needs two numbers")
        if isinstance(left, bool) or isinstance(right, bool):
            raise self.fail(f"{mark!r} needs two numbers")
        if mark in BITWISE_MARKS and (
            isinstance(left, float) or isinstance(right, float)
        ):
            raise self.fail(f"{mark!r} needs two whole numbers")
        return apply(left, right)

    def unary(self) -> EnumValue:
        for mark, apply in (("-", operator.neg), ("+", operator.pos)):
            if self.take_punctuation(mark):
                value = self.unary()
                if not isinstance(value, int | float) or isinstance(value, bool):
                    raise self.fail(f"unary {mark!r} needs a number")
                return apply(value)
        if self.take_punctuation("~"):
            value = self.unary()
            if not isinstance(value, int) or isinstance(value, bool):
                raise self.fail("'~' needs a whole number")
            return ~value
        return self.primary()

    def primary(self) -> EnumValue:
        if self.take_punctuation("("):
            inner = self.expression()
            self.expect(")")
            return inner
        if self.peek().punctuation("{"):
            return self.array("}")
        token = self.take()
        if token.kind is TokenKind.NUMBER:
            return number_of(token.value, self.origin, self.constant)
        if token.kind in (TokenKind.TEXT, TokenKind.CHARACTER):
            return token.value
        if token.kind is TokenKind.NAME:
            return self.named(token)
        raise self.fail(f"unexpected {token.value!r}")

    def named(self, token: Token) -> EnumValue:
        if token.value == "new":
            return self.construction()
        word = self.dotted(token.value)
        if word in WORD_VALUES:
            return WORD_VALUES[word]
        if self.take_punctuation("("):
            arguments = self.array(")")
            if word in ARRAY_BUILDERS:
                return arguments
            return {CALL_KEY: word, ARGUMENTS_KEY: arguments}
        return {SYMBOL_KEY: word}

    def construction(self) -> EnumValue:
        word = self.dotted(self.take().value)
        dimensions = 0
        while self.take_punctuation("["):
            self.expect("]")
            dimensions += 1
        if dimensions:
            return self.array("}")
        self.expect("(")
        return {CALL_KEY: word, ARGUMENTS_KEY: self.array(")")}

    def dotted(self, first: str) -> str:
        parts = [first]
        while not self.done() and self.peek().punctuation("."):
            self.at += 1
            parts.append(self.take().value)
        return ".".join(parts)

    def array(self, closing: str) -> list[EnumValue]:
        if closing == "}":
            self.expect("{")
        values: list[EnumValue] = []
        if self.take_punctuation(closing):
            return values
        values.append(self.expression())
        while self.take_punctuation(","):
            if self.take_punctuation(closing):
                return values
            values.append(self.expression())
        self.expect(closing)
        return values


# test cases


def _read(source: str) -> tuple[EnumValue, ...]:
    from wiki_api.pipeline.enums.lexer import tokenize

    return read_arguments(tokenize(source, "x.java"), "x.java", "CONSTANT")


def test_plain_values_come_back_as_themselves() -> None:
    assert _read('1, 2.5, "text", true, false, null') == (
        1,
        2.5,
        "text",
        True,
        False,
        None,
    )


def test_a_packed_pair_is_folded_to_the_number_it_means() -> None:
    assert _read("50 | 100 << 16") == (6553650,)


def test_arithmetic_follows_the_usual_precedence() -> None:
    assert _read("1 + 2 * 3, (1 + 2) * 3, 8 / 2, 7 % 4") == (7, 9, 4.0, 3)


def test_a_negative_number_survives_the_sign() -> None:
    assert _read("-1, +2, ~0") == (-1, 2, -1)


def test_a_symbol_is_kept_as_a_symbol_rather_than_a_string() -> None:
    assert _read("Skills.WOODCUTTING") == ({SYMBOL_KEY: "Skills.WOODCUTTING"},)


def test_a_construction_keeps_its_name_and_arguments() -> None:
    assert _read("new Animation(867, Priority.HIGH)") == (
        {
            CALL_KEY: "Animation",
            ARGUMENTS_KEY: [867, {SYMBOL_KEY: "Priority.HIGH"}],
        },
    )


def test_an_array_of_either_language_becomes_a_list() -> None:
    assert _read("new int[] { 1604, 1605 }") == ([1604, 1605],)
    assert _read("intArrayOf(1, 2)") == ([1, 2],)
    assert _read("{ 1, 2 }") == ([1, 2],)


def test_an_empty_array_is_still_an_array() -> None:
    assert _read("new int[] { }") == ([],)


def test_an_array_of_arrays_keeps_both_levels() -> None:
    assert _read('new String[][] { { "a", "b" }, { "c" } }') == ([["a", "b"], ["c"]],)
    assert _read("new int[][] { }") == ([],)


def test_a_trailing_comma_inside_an_array_is_allowed() -> None:
    assert _read("intArrayOf(1, 2,)") == ([1, 2],)


def test_no_arguments_reads_as_no_values() -> None:
    assert _read("") == ()


def test_number_literals_of_every_shape_are_read() -> None:
    assert _read("0x1F, 0b1010, 1_000L, 2.5e-3, 1.0f, 25.0") == (
        31,
        10,
        1000,
        0.0025,
        1.0,
        25.0,
    )


def test_arithmetic_over_something_that_is_not_a_number_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableConstant):
        _read('"text" | 1')
    with pytest.raises(UnreadableConstant):
        _read("true + 1")


def test_a_shift_of_a_fraction_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableConstant):
        _read("1.5 << 2")


def test_arguments_that_do_not_close_are_refused() -> None:
    import pytest

    with pytest.raises(UnreadableConstant):
        _read("new int[] { 1, 2")
    with pytest.raises(UnreadableConstant):
        _read("(1 + 2")


def test_a_bad_number_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableConstant):
        number_of("0x", "x.java", "CONSTANT")
    with pytest.raises(UnreadableConstant):
        number_of("1.2.3", "x.java", "CONSTANT")


def test_a_stray_token_after_the_arguments_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableConstant):
        _read("1 2")
