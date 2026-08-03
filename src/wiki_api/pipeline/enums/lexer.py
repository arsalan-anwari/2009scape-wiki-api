"""Split Java and Kotlin source into the tokens the declared-enum reader needs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from wiki_api.pipeline.enums.errors import UnreadableSyntax

LINE_COMMENT: Final = "//"
BLOCK_OPEN: Final = "/*"
BLOCK_CLOSE: Final = "*/"
RAW_QUOTE: Final = '"""'
NAME_START: Final = "_$"
NUMBER_SUFFIXES: Final = "lLfFdD"
OPERATORS: Final = (">>>", "<<", ">>", "->", "::", "==", "!=", "<=", ">=", "&&", "||")
PUNCTUATION: Final = "(){}[],.;:=<>+-*/%|&^~?!@"
ESCAPES: Final = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "0": "\0",
    "s": " ",
    "'": "'",
    '"': '"',
    "\\": "\\",
    "$": "$",
}


class TokenKind(StrEnum):
    """What sort of thing one token is."""

    NAME = "name"
    NUMBER = "number"
    TEXT = "text"
    CHARACTER = "character"
    PUNCTUATION = "punctuation"


@dataclass(frozen=True)
class Token:
    """One token, with the line it started on so an error can point at it."""

    kind: TokenKind
    value: str
    line: int

    def punctuation(self, mark: str) -> bool:
        return self.kind is TokenKind.PUNCTUATION and self.value == mark

    def name(self, word: str) -> bool:
        return self.kind is TokenKind.NAME and self.value == word


class _Scanner:
    def __init__(self, text: str, origin: str) -> None:
        self.text = text
        self.origin = origin
        self.at = 0
        self.line = 1

    def done(self) -> bool:
        return self.at >= len(self.text)

    def peek(self, ahead: int = 0) -> str:
        position = self.at + ahead
        return self.text[position] if position < len(self.text) else ""

    def starts(self, prefix: str) -> bool:
        return self.text.startswith(prefix, self.at)

    def take(self, count: int = 1) -> str:
        taken = self.text[self.at : self.at + count]
        self.line += taken.count("\n")
        self.at += count
        return taken

    def fail(self, detail: str) -> UnreadableSyntax:
        return UnreadableSyntax(self.origin, self.line, detail)


def tokenize(text: str, origin: str) -> tuple[Token, ...]:
    """Read the whole file into tokens, dropping whitespace and comments."""
    scanner = _Scanner(text, origin)
    tokens: list[Token] = []
    while True:
        _skip_dead_space(scanner)
        if scanner.done():
            return tuple(tokens)
        tokens.append(_next_token(scanner))


def _skip_dead_space(scanner: _Scanner) -> None:
    while not scanner.done():
        if scanner.peek().isspace():
            scanner.take()
        elif scanner.starts(LINE_COMMENT):
            while not scanner.done() and scanner.peek() != "\n":
                scanner.take()
        elif scanner.starts(BLOCK_OPEN):
            _skip_block_comment(scanner)
        else:
            return


def _skip_block_comment(scanner: _Scanner) -> None:
    start = scanner.line
    scanner.take(len(BLOCK_OPEN))
    while not scanner.starts(BLOCK_CLOSE):
        if scanner.done():
            raise UnreadableSyntax(scanner.origin, start, "unterminated block comment")
        scanner.take()
    scanner.take(len(BLOCK_CLOSE))


def _next_token(scanner: _Scanner) -> Token:
    line = scanner.line
    character = scanner.peek()
    if scanner.starts(RAW_QUOTE):
        return Token(TokenKind.TEXT, _read_raw_text(scanner), line)
    if character == '"':
        return Token(TokenKind.TEXT, _read_text(scanner), line)
    if character == "'":
        return Token(TokenKind.CHARACTER, _read_character(scanner), line)
    if character.isdigit():
        return Token(TokenKind.NUMBER, _read_number(scanner), line)
    if character.isalpha() or character in NAME_START:
        return Token(TokenKind.NAME, _read_name(scanner), line)
    for operator in OPERATORS:
        if scanner.starts(operator):
            return Token(TokenKind.PUNCTUATION, scanner.take(len(operator)), line)
    if character in PUNCTUATION:
        return Token(TokenKind.PUNCTUATION, scanner.take(), line)
    raise scanner.fail(f"unexpected character {character!r}")


def _read_name(scanner: _Scanner) -> str:
    letters: list[str] = []
    while not scanner.done():
        character = scanner.peek()
        if character.isalnum() or character in NAME_START:
            letters.append(scanner.take())
        else:
            break
    return "".join(letters)


def _read_number(scanner: _Scanner) -> str:
    digits: list[str] = []
    while not scanner.done():
        character = scanner.peek()
        exponent = character in "+-" and digits and digits[-1] in "eE"
        if character.isalnum() or character == "_" or character == "." or exponent:
            digits.append(scanner.take())
        else:
            break
    return "".join(digits)


def _read_text(scanner: _Scanner) -> str:
    start = scanner.line
    scanner.take()
    letters: list[str] = []
    while True:
        if scanner.done() or scanner.peek() == "\n":
            raise UnreadableSyntax(scanner.origin, start, "unterminated string")
        if scanner.peek() == '"':
            scanner.take()
            return "".join(letters)
        letters.append(_read_letter(scanner))


def _read_raw_text(scanner: _Scanner) -> str:
    start = scanner.line
    scanner.take(len(RAW_QUOTE))
    letters: list[str] = []
    while not scanner.starts(RAW_QUOTE):
        if scanner.done():
            raise UnreadableSyntax(scanner.origin, start, "unterminated raw string")
        letters.append(scanner.take())
    scanner.take(len(RAW_QUOTE))
    return "".join(letters)


def _read_character(scanner: _Scanner) -> str:
    start = scanner.line
    scanner.take()
    letter = _read_letter(scanner)
    if scanner.peek() != "'":
        raise UnreadableSyntax(scanner.origin, start, "unterminated character literal")
    scanner.take()
    return letter


def _read_letter(scanner: _Scanner) -> str:
    if scanner.peek() != "\\":
        return scanner.take()
    scanner.take()
    marker = scanner.take()
    if marker == "u":
        return chr(int(scanner.take(4), 16))
    escaped = ESCAPES.get(marker)
    if escaped is None:
        raise scanner.fail(f"unknown escape {marker!r}")
    return escaped


# test cases


def test_names_numbers_and_punctuation_come_back_apart() -> None:
    tokens = tokenize("BRONZE(1, 2)", "Bars.java")
    assert [token.kind for token in tokens] == [
        TokenKind.NAME,
        TokenKind.PUNCTUATION,
        TokenKind.NUMBER,
        TokenKind.PUNCTUATION,
        TokenKind.NUMBER,
        TokenKind.PUNCTUATION,
    ]
    assert tokens[0].value == "BRONZE"


def test_comments_of_both_shapes_are_dropped() -> None:
    source = """
    // a line about the enum
    ONE(1), /* and a block
    over two lines */ TWO(2)
    """
    values = [token.value for token in tokenize(source, "x.kt")]
    assert values == ["ONE", "(", "1", ")", ",", "TWO", "(", "2", ")"]


def test_a_string_keeps_its_escapes_resolved() -> None:
    tokens = tokenize(r'NAME("Doric\'s Quest\n")', "Quests.kt")
    text = next(token for token in tokens if token.kind is TokenKind.TEXT)
    assert text.value == "Doric's Quest\n"


def test_a_unicode_escape_becomes_the_character_it_names() -> None:
    tokens = tokenize(r'A("A")', "x.java")
    assert tokens[2].value == "A"


def test_a_raw_string_survives_its_line_breaks() -> None:
    tokens = tokenize('A("""one\ntwo""")', "x.kt")
    assert tokens[2].value == "one\ntwo"


def test_shifts_and_arrows_stay_one_token() -> None:
    values = [token.value for token in tokenize("50 | 100 << 16", "x.java")]
    assert values == ["50", "|", "100", "<<", "16"]


def test_a_line_is_recorded_so_an_error_can_point_at_it() -> None:
    tokens = tokenize("A(1)\nB(2)", "x.kt")
    assert tokens[0].line == 1
    assert tokens[-1].line == 2


def test_an_unterminated_string_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableSyntax):
        tokenize('A("oops)', "x.kt")


def test_an_unterminated_block_comment_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableSyntax):
        tokenize("/* forever", "x.kt")


def test_an_unknown_escape_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableSyntax):
        tokenize(r'A("\q")', "x.kt")


def test_an_unknown_character_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableSyntax):
        tokenize("A #", "x.kt")


def test_a_number_keeps_its_suffix_and_separators() -> None:
    values = [token.value for token in tokenize("1_000L 0x1F 2.5e-3", "x.java")]
    assert values == ["1_000L", "0x1F", "2.5e-3"]


def test_a_character_literal_is_read_as_one_letter() -> None:
    tokens = tokenize("A('x')", "x.java")
    assert tokens[2].kind is TokenKind.CHARACTER
    assert tokens[2].value == "x"


def test_a_token_can_be_asked_what_it_is() -> None:
    tokens = tokenize("ONE(", "x.kt")
    assert tokens[0].name("ONE")
    assert tokens[1].punctuation("(")
    assert not tokens[0].punctuation("(")


def test_an_unterminated_character_literal_is_refused() -> None:
    import pytest

    with pytest.raises(UnreadableSyntax):
        tokenize("A('xy')", "x.java")
