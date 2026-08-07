"""Read one declared enum out of a Java or Kotlin file as a table with named columns."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.enums.errors import (
    AmbiguousConstructor,
    ColumnMismatch,
    EnumNotFound,
)
from wiki_api.pipeline.enums.lexer import Token, TokenKind, tokenize
from wiki_api.pipeline.enums.values import CALL_KEY, EnumValue, read_arguments

if TYPE_CHECKING:
    from collections.abc import Sequence

ENUM_WORD: Final = "enum"
CLASS_WORD: Final = "class"
NEW_WORD: Final = "new"
KOTLIN_SUFFIX: Final = ".kt"
NAME_MODIFIERS: Final = frozenset({"val", "var", "vararg", "final", "private"})
OPENING: Final = {"(": ")", "[": "]", "{": "}"}
CLOSING: Final = {")": "(", "]": "[", "}": "{"}
WHOLE_TYPES: Final = frozenset(
    {"int", "long", "short", "byte", "Int", "Long", "Short", "Byte"}
)
DECIMAL_TYPES: Final = frozenset({"double", "float", "Double", "Float"})
BOOLEAN_TYPES: Final = frozenset({"boolean", "Boolean"})
TEXT_TYPES: Final = frozenset({"String", "char", "Char", "CharSequence"})
OPAQUE_TYPES: Final = frozenset({"Object", "Any", "Array", "List", "Set", "Collection"})
KOTLIN_ARRAY_TYPES: Final = frozenset(
    {
        "Array",
        "IntArray",
        "LongArray",
        "ShortArray",
        "ByteArray",
        "DoubleArray",
        "FloatArray",
        "BooleanArray",
        "CharArray",
        "List",
        "Set",
    }
)


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
class _Parameter:
    name: str
    type_name: str
    dimensions: int

    @property
    def declared(self) -> str:
        return self.type_name + "[]" * self.dimensions

    def element(self) -> _Parameter:
        return _Parameter(
            name=self.name,
            type_name=self.type_name,
            dimensions=max(self.dimensions - 1, 0),
        )


@dataclass(frozen=True)
class _Constant:
    name: str
    arguments: tuple[EnumValue, ...]
    types: tuple[str, ...]


@dataclass(frozen=True)
class _Signature:
    parameters: tuple[_Parameter, ...]
    variadic: bool

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(parameter.name for parameter in self.parameters)

    def accepts(self, count: int) -> bool:
        if self.variadic:
            return count >= len(self.parameters) - 1
        return count == len(self.parameters)

    def fits(self, constant: _Constant) -> bool:
        fixed = len(self.parameters) - 1 if self.variadic else len(self.parameters)
        head = zip(
            self.parameters[:fixed],
            constant.arguments[:fixed],
            constant.types[:fixed],
            strict=True,
        )
        if any(not _fits(*entry) for entry in head):
            return False
        if not self.variadic:
            return True
        tail = self.parameters[-1].element()
        return all(
            _fits(tail, argument, named)
            for argument, named in zip(
                constant.arguments[fixed:], constant.types[fixed:], strict=True
            )
        )

    def bind(self, arguments: Sequence[EnumValue]) -> dict[str, EnumValue]:
        if not self.variadic:
            return dict(zip(self.names, arguments, strict=True))
        fixed = len(self.parameters) - 1
        bound: dict[str, EnumValue] = dict(
            zip(self.names[:fixed], arguments[:fixed], strict=True)
        )
        bound[self.names[-1]] = list(arguments[fixed:])
        return bound


def _fits(parameter: _Parameter, argument: EnumValue, named: str) -> bool:
    if named and parameter.type_name not in OPAQUE_TYPES:
        return named == parameter.declared
    if argument is None:
        return True
    if isinstance(argument, list):
        element = parameter.element()
        return bool(parameter.dimensions) and all(
            _fits(element, entry, "") for entry in argument
        )
    return not parameter.dimensions and _element_fits(parameter.type_name, argument)


def _element_fits(type_name: str, argument: EnumValue) -> bool:
    if argument is None or type_name in OPAQUE_TYPES:
        return True
    if isinstance(argument, dict):
        called = argument.get(CALL_KEY)
        return not isinstance(called, str) or called.rsplit(".", 1)[-1] == type_name
    if isinstance(argument, bool):
        return type_name in BOOLEAN_TYPES
    if isinstance(argument, int):
        return type_name in WHOLE_TYPES or type_name in DECIMAL_TYPES
    if isinstance(argument, float):
        return type_name in DECIMAL_TYPES
    if isinstance(argument, str):
        return type_name in TEXT_TYPES
    return False


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
            _row(constant, signatures, source_file) for constant in constants
        ),
    )


def _row(
    constant: _Constant, signatures: Sequence[_Signature], source_file: str
) -> EnumConstant:
    count = len(constant.arguments)
    if not signatures and not count:
        return EnumConstant(name=constant.name)
    matching = [signature for signature in signatures if signature.accepts(count)]
    if not matching:
        declared = len(signatures[0].parameters) if signatures else 0
        raise ColumnMismatch(source_file, constant.name, count, declared)
    if len(matching) > 1:
        fitting = [signature for signature in matching if signature.fits(constant)]
        if len(fitting) != 1:
            raise AmbiguousConstructor(source_file, constant.name, count, len(matching))
        matching = fitting
    return EnumConstant(name=constant.name, values=matching[0].bind(constant.arguments))


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
    parameters = tuple(_parameter_of(part, language) for part in parts)
    signature = _Signature(
        parameters=parameters, variadic=bool(parts) and _variadic(parts[-1])
    )
    return signature, after


def _parameter_of(part: Sequence[Token], language: Language) -> _Parameter:
    type_name = _parameter_type(part, language)
    return _Parameter(
        name=_parameter_name(part, language),
        type_name=type_name,
        dimensions=_dimensions(part, type_name, language),
    )


def _variadic(part: Sequence[Token]) -> bool:
    dots = sum(1 for token in part if token.punctuation("."))
    return dots >= 3 or any(token.name("vararg") for token in part)


def _parameter_name(part: Sequence[Token], language: Language) -> str:
    if language is Language.KOTLIN:
        for at, token in enumerate(part):
            if token.punctuation(":") and at:
                return part[at - 1].value
    return _last_name(part)


def _parameter_type(part: Sequence[Token], language: Language) -> str:
    if language is Language.KOTLIN:
        for at, token in enumerate(part):
            if token.punctuation(":"):
                return _first_name(part[at + 1 :])
        return ""
    return _first_name(part)


def _dimensions(part: Sequence[Token], type_name: str, language: Language) -> int:
    if _variadic(part):
        return 1
    if language is Language.KOTLIN:
        return 1 if type_name in KOTLIN_ARRAY_TYPES else 0
    return sum(1 for token in part if token.punctuation("["))


def _first_name(part: Sequence[Token]) -> str:
    for token in part:
        if token.kind is TokenKind.NAME and token.value not in NAME_MODIFIERS:
            return token.value
    return ""


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
) -> tuple[list[_Constant], int]:
    constants: list[_Constant] = []
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
        types: tuple[str, ...] = ()
        if _is_open(tokens, at):
            inner, at = _bracketed(tokens, at)
            arguments = read_arguments(inner, source_file, name)
            types = _argument_types(inner, len(arguments))
        if at < len(tokens) and tokens[at].punctuation("{"):
            _, at = _bracketed(tokens, at)
        constants.append(_Constant(name=name, arguments=arguments, types=types))
    return constants, at


def _argument_types(tokens: Sequence[Token], count: int) -> tuple[str, ...]:
    named = tuple(_constructed_type(part) for part in _split(tokens))
    return named if len(named) == count else ("",) * count


def _constructed_type(part: Sequence[Token]) -> str:
    if len(part) < 2 or not part[0].name(NEW_WORD):
        return ""
    if part[1].kind is not TokenKind.NAME:
        return ""
    dimensions, at = 0, 2
    while at + 1 < len(part):
        if not part[at].punctuation("[") or not part[at + 1].punctuation("]"):
            break
        dimensions += 1
        at += 2
    return part[1].value + "[]" * dimensions


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


_SAME_ARITY: Final = """
public enum Decoration {
    PORTAL(13615, 8173, 5, new Item[] { new Item(8778) }),
    SHUTTERED(new int[] { 13253, 13226 }, 8076, 49, new Item[] { new Item(960) }),
    DEAD_TREE(13411, 8173, 5, new int[] { 1 }, new Item[] { new Item(8417) }),
    ARMOUR(13491, 8270, 28, new Item[] { new Item(1159) },
            new Item[] { new Item(1121) });
    Decoration(int objectId, int face, int level, Item[] items) { }
    Decoration(int[] objectIds, int face, int level, Item[] items) { }
    Decoration(int objectId, int face, int level, int[] tools, Item[] items) { }
    Decoration(int objectId, int face, int level, Item[] items, Item[] refunds) { }
}
"""


def test_an_array_parameter_tells_two_constructors_of_one_arity_apart() -> None:
    table = read_enum(_SAME_ARITY, "Decoration", "Decoration.java")
    rows = {constant.name: constant.values for constant in table.constants}
    assert rows["PORTAL"]["objectId"] == 13615
    assert rows["SHUTTERED"]["objectIds"] == [13253, 13226]
    assert "objectIds" not in rows["PORTAL"]


def test_the_element_type_tells_two_array_constructors_apart() -> None:
    table = read_enum(_SAME_ARITY, "Decoration", "Decoration.java")
    rows = {constant.name: constant.values for constant in table.constants}
    assert rows["DEAD_TREE"]["tools"] == [1]
    assert "refunds" not in rows["DEAD_TREE"]
    assert "tools" not in rows["ARMOUR"]
    assert rows["ARMOUR"]["refunds"] == [{"call": "Item", "arguments": [1121]}]


def test_a_constructed_argument_tells_two_variadic_constructors_apart() -> None:
    source = """
    public enum PrayerType {
        THICK_SKIN(1, 12, 83, Cat.BLUE, Sounds.THICK, new Bonus(1, 0.05)),
        RETRIBUTION(46, 12, 98, Cat.BROWN, Cat.MAGENTA, new Audio(2682)),
        PIETY(70, 2, 1053, Cat.PINK, Sounds.PIETY, 70, new Bonus(1, 0.25));
        PrayerType(int level, int drain, int config, Cat rule, int soundId,
                Bonus... bonuses) { }
        PrayerType(int level, int drain, int config, Cat rule, int soundId,
                int defenceReq, Bonus... bonuses) { }
        PrayerType(int level, int drain, int config, Cat rule, Cat second,
                Audio audio, Bonus... bonuses) { }
    }
    """
    rows = {
        constant.name: constant.values
        for constant in read_enum(source, "PrayerType", "PrayerType.java").constants
    }
    assert "defenceReq" not in rows["THICK_SKIN"]
    assert rows["RETRIBUTION"]["audio"] == {"call": "Audio", "arguments": [2682]}
    assert rows["PIETY"]["defenceReq"] == 70


def test_an_ambiguity_the_arguments_cannot_settle_is_refused() -> None:
    import pytest

    source = """
    public enum Thing {
        ONE(1, 2);
        Thing(int a, int b) { }
        Thing(int c, int d) { }
    }
    """
    with pytest.raises(AmbiguousConstructor):
        read_enum(source, "Thing", "Thing.java")


def test_a_parameter_may_be_an_array_of_arrays() -> None:
    source = """
    public enum DiaryType {
        KARAMJA("Karamja", 11, new String[] { "Easy" },
                new String[][] { { "Pick 5 bananas" } });
        DiaryType(String name, int child, String[] levels, String[][] tasks) { }
    }
    """
    table = read_enum(source, "DiaryType", "DiaryType.java")
    assert table.constants[0].values["tasks"] == [["Pick 5 bananas"]]


def test_a_variadic_constructor_accepts_an_empty_tail() -> None:
    source = """
    public enum Master {
        NOBODY(1);
        private Master(int npcId, Task... tasks) { }
    }
    """
    table = read_enum(source, "Master", "Master.java")
    assert table.constants[0].values == {"npcId": 1, "tasks": []}
