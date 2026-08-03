"""Read one declared enum out of a Java or Kotlin file as a table with named columns."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.enums.errors import ColumnMismatch, EnumNotFound
from wiki_api.pipeline.enums.lexer import Token, TokenKind, tokenize
from wiki_api.pipeline.enums.values import EnumValue, read_arguments

if TYPE_CHECKING:
    from collections.abc import Sequence

ENUM_WORD: Final = "enum"
CLASS_WORD: Final = "class"
KOTLIN_SUFFIX: Final = ".kt"
NAME_MODIFIERS: Final = frozenset({"val", "var", "vararg", "final", "private"})
OPENING: Final = {"(": ")", "[": "]", "{": "}"}
CLOSING: Final = {")": "(", "]": "[", "}": "{"}


class Language(StrEnum):
    """Which of the two languages a declared enum is written in."""

    JAVA = "java"
    KOTLIN = "kotlin"

    @classmethod
    def of(cls, filename: str) -> Language:
        return cls.KOTLIN if filename.endswith(KOTLIN_SUFFIX) else cls.JAVA


class EnumConstant(BaseModel):
    """One constant, its arguments keyed by the constructor parameter they filled."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    values: dict[str, EnumValue] = Field(default_factory=dict)


class EnumTable(BaseModel):
    """One declared enum read as rows and named columns."""

    model_config = ConfigDict(frozen=True)

    enum: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    language: Language
    columns: tuple[str, ...] = ()
    constants: tuple[EnumConstant, ...] = ()

    def column(self, name: str) -> bool:
        return name in self.columns


@dataclass(frozen=True)
class _Signature:
    names: tuple[str, ...]
    variadic: bool

    def accepts(self, count: int) -> bool:
        if self.variadic:
            return count >= len(self.names) - 1
        return count == len(self.names)

    def bind(self, arguments: Sequence[EnumValue]) -> dict[str, EnumValue]:
        if not self.variadic:
            return dict(zip(self.names, arguments, strict=True))
        fixed = len(self.names) - 1
        bound: dict[str, EnumValue] = dict(
            zip(self.names[:fixed], arguments[:fixed], strict=True)
        )
        bound[self.names[-1]] = list(arguments[fixed:])
        return bound


def read_enum(text: str, name: str, source_file: str) -> EnumTable:
    """Read the named enum out of one file, refusing anything it cannot fold."""
    language = Language.of(source_file)
    tokens = tokenize(text, source_file)
    at = _find_declaration(tokens, name, source_file)
    signatures: list[_Signature] = []
    if language is Language.KOTLIN and _is_open(tokens, at):
        signature, at = _read_parameters(tokens, at, language)
        signatures.append(signature)
    body = _skip_to_body(tokens, at)
    constants, after = _read_constants(tokens, body, source_file)
    if language is Language.JAVA:
        signatures.extend(_java_constructors(tokens, after, name, language))
    widest = max(signatures, key=lambda signature: len(signature.names), default=None)
    return EnumTable(
        enum=name,
        source_file=source_file,
        language=language,
        columns=widest.names if widest else (),
        constants=tuple(
            _row(constant, arguments, signatures, source_file)
            for constant, arguments in constants
        ),
    )


def _row(
    constant: str,
    arguments: tuple[EnumValue, ...],
    signatures: Sequence[_Signature],
    source_file: str,
) -> EnumConstant:
    if not signatures and not arguments:
        return EnumConstant(name=constant)
    matching = [
        signature for signature in signatures if signature.accepts(len(arguments))
    ]
    if len(matching) != 1:
        declared = len(signatures[0].names) if signatures else 0
        raise ColumnMismatch(source_file, constant, len(arguments), declared)
    return EnumConstant(name=constant, values=matching[0].bind(arguments))


def _find_declaration(tokens: Sequence[Token], name: str, source_file: str) -> int:
    for at, token in enumerate(tokens):
        if not token.name(ENUM_WORD):
            continue
        after = at + 1
        if after < len(tokens) and tokens[after].name(CLASS_WORD):
            after += 1
        if after < len(tokens) and tokens[after].name(name):
            return after + 1
    raise EnumNotFound(source_file, name)


def _is_open(tokens: Sequence[Token], at: int) -> bool:
    return at < len(tokens) and tokens[at].punctuation("(")


def _read_parameters(
    tokens: Sequence[Token], at: int, language: Language
) -> tuple[_Signature, int]:
    inner, after = _bracketed(tokens, at)
    parts = _split(inner)
    names = tuple(_parameter_name(part, language) for part in parts)
    return _Signature(names=names, variadic=bool(parts) and _variadic(parts[-1])), after


def _variadic(part: Sequence[Token]) -> bool:
    dots = sum(1 for token in part if token.punctuation("."))
    return dots >= 3 or any(token.name("vararg") for token in part)


def _parameter_name(part: Sequence[Token], language: Language) -> str:
    if language is Language.KOTLIN:
        for at, token in enumerate(part):
            if token.punctuation(":") and at:
                return part[at - 1].value
    return _last_name(part)


def _last_name(part: Sequence[Token]) -> str:
    for token in reversed(part):
        if token.kind is TokenKind.NAME and token.value not in NAME_MODIFIERS:
            return token.value
    return ""


def _split(tokens: Sequence[Token]) -> list[list[Token]]:
    parts: list[list[Token]] = []
    current: list[Token] = []
    depth = 0
    for token in tokens:
        if token.kind is TokenKind.PUNCTUATION and token.value in OPENING:
            depth += 1
        elif token.kind is TokenKind.PUNCTUATION and token.value in CLOSING:
            depth -= 1
        if depth == 0 and token.punctuation(","):
            parts.append(current)
            current = []
            continue
        current.append(token)
    if current:
        parts.append(current)
    return parts


def _bracketed(tokens: Sequence[Token], at: int) -> tuple[Sequence[Token], int]:
    closing = OPENING[tokens[at].value]
    depth = 0
    for end in range(at, len(tokens)):
        token = tokens[end]
        if token.kind is not TokenKind.PUNCTUATION:
            continue
        if token.value in OPENING:
            depth += 1
        elif token.value in CLOSING:
            depth -= 1
            if depth == 0 and token.value == closing:
                return tokens[at + 1 : end], end + 1
    return tokens[at + 1 :], len(tokens)


def _skip_to_body(tokens: Sequence[Token], at: int) -> int:
    for end in range(at, len(tokens)):
        if tokens[end].punctuation("{"):
            return end + 1
    return len(tokens)


def _read_constants(
    tokens: Sequence[Token], at: int, source_file: str
) -> tuple[list[tuple[str, tuple[EnumValue, ...]]], int]:
    constants: list[tuple[str, tuple[EnumValue, ...]]] = []
    while at < len(tokens):
        token = tokens[at]
        if token.punctuation(";") or token.punctuation("}"):
            return constants, at + 1
        if token.punctuation(",") or token.punctuation("@"):
            at += 1
            continue
        if token.kind is not TokenKind.NAME:
            return constants, at
        name = token.value
        at += 1
        arguments: tuple[EnumValue, ...] = ()
        if _is_open(tokens, at):
            inner, at = _bracketed(tokens, at)
            arguments = read_arguments(inner, source_file, name)
        if at < len(tokens) and tokens[at].punctuation("{"):
            _, at = _bracketed(tokens, at)
        constants.append((name, arguments))
    return constants, at


def _java_constructors(
    tokens: Sequence[Token], at: int, name: str, language: Language
) -> list[_Signature]:
    signatures: list[_Signature] = []
    for end in range(at, len(tokens) - 1):
        if tokens[end].name(name) and tokens[end + 1].punctuation("("):
            signature, after = _read_parameters(tokens, end + 1, language)
            if after < len(tokens) and tokens[after].punctuation("{"):
                signatures.append(signature)
    return signatures


# test cases


_KOTLIN: Final = """
package content.data

enum class Quests(val questName: String) {
    DEATH_PLATEAU("Death Plateau"),
    DORICS_QUEST("Doric's Quest"),
    ;

    companion object {
        fun forName(name: String) = entries.first { it.questName == name }
    }
}
"""

_JAVA: Final = """
package content.global.skill.gather;

public enum SkillingResource {
    STANDARD_TREE_1(1276, 1, 0.05, 50 | 100 << 16, 25.0, "tree", Skills.WOODCUTTING),
    OAK_TREE(1281, 15, 0.125, 25 | 50 << 16, 37.5, "oak", Skills.WOODCUTTING);

    private SkillingResource(int id, int level, double rate, int respawnRate,
            double experience, String name, int skillId) {
        this.id = id;
    }
}
"""


def test_a_kotlin_enum_reads_its_constructor_names_as_columns() -> None:
    table = read_enum(_KOTLIN, "Quests", "Quests.kt")
    assert table.language is Language.KOTLIN
    assert table.columns == ("questName",)
    assert len(table.constants) == 2
    assert table.constants[0].name == "DEATH_PLATEAU"
    assert table.constants[0].values == {"questName": "Death Plateau"}
    assert table.constants[1].values == {"questName": "Doric's Quest"}


def test_a_java_enum_reads_its_constructor_names_as_columns() -> None:
    table = read_enum(_JAVA, "SkillingResource", "SkillingResource.java")
    assert table.language is Language.JAVA
    assert table.columns == (
        "id",
        "level",
        "rate",
        "respawnRate",
        "experience",
        "name",
        "skillId",
    )
    first = table.constants[0]
    assert first.values["id"] == 1276
    assert first.values["respawnRate"] == 6553650
    assert first.values["skillId"] == {"symbol": "Skills.WOODCUTTING"}


def test_a_table_says_which_columns_it_carries() -> None:
    table = read_enum(_KOTLIN, "Quests", "Quests.kt")
    assert table.column("questName")
    assert not table.column("level")


def test_an_enum_that_is_not_there_is_refused() -> None:
    import pytest

    with pytest.raises(EnumNotFound):
        read_enum(_KOTLIN, "Bars", "Quests.kt")


def test_a_constant_with_the_wrong_number_of_arguments_is_refused() -> None:
    import pytest

    source = """
    enum class Small(val a: Int, val b: Int) {
        ONE(1),
    }
    """
    with pytest.raises(ColumnMismatch):
        read_enum(source, "Small", "Small.kt")


def test_constants_carrying_a_body_are_read_past() -> None:
    source = """
    public enum Style {
        LOUD(1) { public void play() { ring(); } },
        QUIET(2);
        private Style(int volume) { }
    }
    """
    table = read_enum(source, "Style", "Style.java")
    assert [constant.name for constant in table.constants] == ["LOUD", "QUIET"]
    assert table.constants[0].values == {"volume": 1}


def test_an_enum_with_no_arguments_has_no_columns() -> None:
    table = read_enum("enum class Colour { RED, GREEN }", "Colour", "Colour.kt")
    assert table.columns == ()
    assert [constant.name for constant in table.constants] == ["RED", "GREEN"]
    assert table.constants[0].values == {}


def test_the_widest_constructor_names_the_columns() -> None:
    source = """
    public enum Task {
        SHORT(1),
        LONG(1, "why");
        private Task(int level) { }
        private Task(int level, String reason) { }
    }
    """
    table = read_enum(source, "Task", "Task.java")
    assert table.columns == ("level", "reason")
    assert table.constants[0].values == {"level": 1}
    assert table.constants[1].values == {"level": 1, "reason": "why"}


def test_an_array_argument_survives_as_a_list() -> None:
    source = """
    public enum Tasks {
        ANKOU(40, new int[] { 4381, 4382 }, true);
        private Tasks(int level, int[] npcs, boolean members) { }
    }
    """
    table = read_enum(source, "Tasks", "Tasks.java")
    assert table.constants[0].values == {
        "level": 40,
        "npcs": [4381, 4382],
        "members": True,
    }


def test_the_language_is_taken_from_the_filename() -> None:
    assert Language.of("Quests.kt") is Language.KOTLIN
    assert Language.of("Tasks.java") is Language.JAVA


def test_a_variadic_constructor_gathers_its_tail_into_one_column() -> None:
    source = """
    public enum Master {
        TURAEL(8273, new Task(1), new Task(2), new Task(3));
        private Master(int npcId, Task... tasks) { }
    }
    """
    table = read_enum(source, "Master", "Master.java")
    assert table.columns == ("npcId", "tasks")
    tasks = table.constants[0].values["tasks"]
    assert isinstance(tasks, list)
    assert len(tasks) == 3


def test_a_variadic_constructor_accepts_an_empty_tail() -> None:
    source = """
    public enum Master {
        NOBODY(1);
        private Master(int npcId, Task... tasks) { }
    }
    """
    table = read_enum(source, "Master", "Master.java")
    assert table.constants[0].values == {"npcId": 1, "tasks": []}
