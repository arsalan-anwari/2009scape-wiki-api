"""Read the game's named id constants out of the library its code compiles against."""

from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.enums.errors import EnumNotFound

DECLARATION: Final = re.compile(
    r"^\s*(?:@\w+\s+)*const\s+val\s+(\w+)\s*(?::\s*Int\s*)?=\s*(-?\d+)\s*$",
    re.MULTILINE,
)
OBJECT: Final = re.compile(r"\bobject\s+(\w+)\s*\{")
BODY_END: Final = re.compile(r"^\}", re.MULTILINE)


class ConstantTable(BaseModel):
    """One `object` of named ids, read as a lookup a symbol can be resolved through."""

    model_config = ConfigDict(frozen=True)

    object_name: str = Field(min_length=1)
    source_file: str = Field(min_length=1)
    ids: dict[str, int] = Field(default_factory=dict)

    def id_of(self, symbol: str) -> int | None:
        """The number behind a symbol written as `Items.RAW_SHRIMPS_317` or bare."""
        qualifier, separator, name = symbol.rpartition(".")
        if separator and qualifier != self.object_name:
            return None
        return self.ids.get(name)


def read_constants(source: str, object_name: str, source_file: str) -> ConstantTable:
    """Read every `const val NAME = 123` the named object declares."""
    found = next(
        (match for match in OBJECT.finditer(source) if match.group(1) == object_name),
        None,
    )
    if found is None:
        raise EnumNotFound(source_file, object_name)
    rest = source[found.end() :]
    closing = BODY_END.search(rest)
    body = rest[: closing.start()] if closing else rest
    return ConstantTable(
        object_name=object_name,
        source_file=source_file,
        ids={name: int(value) for name, value in DECLARATION.findall(body)},
    )


class Constants(BaseModel):
    """Every constants object staging read, asked as one lookup."""

    model_config = ConfigDict(frozen=True)

    tables: tuple[ConstantTable, ...] = ()

    def id_of(self, symbol: str) -> int | None:
        """The number a qualified symbol names, or none when nothing declares it."""
        for table in self.tables:
            found = table.id_of(symbol)
            if found is not None:
                return found
        return None

    @property
    def count(self) -> int:
        return sum(len(table.ids) for table in self.tables)


# test cases

SAMPLE: Final = """
package org.rs09.consts

object Items {
    const val RAW_SHRIMPS_317 = 317
    const val NOTHING = -1
}

object NPCs {
    const val FISHING_SPOT_952 = 952
}
"""


def test_a_constants_object_reads_as_a_lookup() -> None:
    table = read_constants(SAMPLE, "Items", "Items.kt")
    assert table.ids == {"RAW_SHRIMPS_317": 317, "NOTHING": -1}
    assert table.id_of("Items.RAW_SHRIMPS_317") == 317
    assert table.id_of("RAW_SHRIMPS_317") == 317


def test_a_symbol_qualified_by_another_object_is_not_answered() -> None:
    table = read_constants(SAMPLE, "Items", "Items.kt")
    assert table.id_of("NPCs.RAW_SHRIMPS_317") is None


def test_only_the_named_object_is_read() -> None:
    assert read_constants(SAMPLE, "NPCs", "NPCs.kt").ids == {"FISHING_SPOT_952": 952}


def test_an_object_nothing_declares_is_refused() -> None:
    import pytest

    with pytest.raises(EnumNotFound):
        read_constants(SAMPLE, "Scenery", "Scenery.kt")


def test_a_lookup_over_several_objects_answers_for_each() -> None:
    constants = Constants(
        tables=(
            read_constants(SAMPLE, "Items", "Items.kt"),
            read_constants(SAMPLE, "NPCs", "NPCs.kt"),
        )
    )
    assert constants.id_of("Items.RAW_SHRIMPS_317") == 317
    assert constants.id_of("NPCs.FISHING_SPOT_952") == 952
    assert constants.id_of("NPCs.NOTHING") is None
    assert constants.count == 3
