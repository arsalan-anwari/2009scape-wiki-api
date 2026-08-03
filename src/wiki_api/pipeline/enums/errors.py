"""Errors the declared-enum reader raises, each naming the file it was reading."""

from __future__ import annotations

from wiki_api.domain.errors import KnowledgeError


class EnumReadError(KnowledgeError):
    """Base class for anything that stops an enum being read."""


class UnreadableSyntax(EnumReadError):
    """The reader met a character it has no rule for."""

    def __init__(self, origin: str, line: int, detail: str) -> None:
        super().__init__(f"{origin}:{line} cannot be read: {detail}")
        self.origin = origin
        self.line = line
        self.detail = detail


class EnumNotFound(EnumReadError):
    """The file holds no enum by the declared name."""

    def __init__(self, origin: str, name: str) -> None:
        super().__init__(f"{origin} declares no enum called {name}")
        self.origin = origin
        self.name = name


class UnreadableConstant(EnumReadError):
    """A constant's arguments fall outside the grammar the reader accepts."""

    def __init__(self, origin: str, constant: str, detail: str) -> None:
        super().__init__(f"{origin} constant {constant} cannot be read: {detail}")
        self.origin = origin
        self.constant = constant
        self.detail = detail


class ColumnMismatch(EnumReadError):
    """A constant carries a different number of arguments than the enum declares."""

    def __init__(self, origin: str, constant: str, found: int, declared: int) -> None:
        super().__init__(
            f"{origin} constant {constant} passes {found} arguments, "
            f"the constructor declares {declared}"
        )
        self.origin = origin
        self.constant = constant
        self.found = found
        self.declared = declared


# test cases


def test_every_reader_error_is_a_knowledge_error() -> None:
    errors = (
        UnreadableSyntax("Quests.kt", 4, "unterminated string"),
        EnumNotFound("Quests.kt", "Quests"),
        UnreadableConstant("Quests.kt", "DEATH_PLATEAU", "unsupported call"),
        ColumnMismatch("Quests.kt", "DEATH_PLATEAU", 2, 1),
    )
    assert all(isinstance(error, EnumReadError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_a_column_mismatch_names_both_counts() -> None:
    error = ColumnMismatch("Bars.java", "BRONZE", 3, 4)
    assert "3 arguments" in str(error)
    assert "declares 4" in str(error)
