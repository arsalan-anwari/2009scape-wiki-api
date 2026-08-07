from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from wiki_api.pipeline.enums import read_enum
from wiki_api.pipeline.enums.errors import AmbiguousConstructor
from wiki_api.pipeline.enums.reader import EnumTable

if TYPE_CHECKING:
    from pathlib import Path

ENUM = "Overloaded"
FILENAME = "Overloaded.java"


def _fixture() -> str:
    from tests.artifact import FIXTURE_KNOWLEDGE

    path = FIXTURE_KNOWLEDGE.parent / "sources" / "tables" / FILENAME
    return path.read_text(encoding="utf-8")


def _table() -> EnumTable:
    return read_enum(_fixture(), ENUM, FILENAME)


def _rows(table: EnumTable) -> dict[str, dict[str, Any]]:
    return {constant.name: dict(constant.values) for constant in table.constants}


def test_every_constant_of_an_overloaded_enum_is_read() -> None:
    table = _table()
    assert [constant.name for constant in table.constants] == [
        "CURTAINS",
        "BASIC_WINDOW",
        "PORTAL",
        "SHUTTERED",
        "DEAD_TREE",
        "MITHRIL_ARMOUR",
        "GLORY_MOUNT",
        "NOTICE_BOARD",
    ]


def test_two_constructors_of_one_arity_bind_to_the_right_columns() -> None:
    rows = _rows(_table())
    assert rows["PORTAL"]["objectId"] == 13615
    assert rows["SHUTTERED"]["objectIds"] == [13253, 13226, 13235]
    assert "objectIds" not in rows["PORTAL"]
    assert "objectId" not in rows["SHUTTERED"]


def test_two_array_constructors_of_one_arity_are_told_apart_by_element_type() -> None:
    rows = _rows(_table())
    assert rows["DEAD_TREE"]["tools"] == [{"symbol": "BuildingUtils.WATERING_CAN"}]
    assert "refundItems" not in rows["DEAD_TREE"]
    assert "tools" not in rows["MITHRIL_ARMOUR"]
    assert rows["MITHRIL_ARMOUR"]["refundItems"] == [
        {"call": "Item", "arguments": [{"symbol": "Items.MITHRIL_FULL_HELM_1159"}, 1]}
    ]


def test_a_column_that_is_an_array_of_arrays_keeps_both_levels() -> None:
    rows = _rows(_table())
    assert rows["NOTICE_BOARD"]["achievements"] == [
        ["Pick 5 bananas"],
        ["Kill a lesser demon"],
    ]
    assert rows["NOTICE_BOARD"]["levelNames"] == ["Easy", "Medium"]


def test_the_widest_constructor_still_names_the_columns() -> None:
    table = _table()
    assert table.columns == (
        "objectId",
        "interfaceItem",
        "level",
        "experience",
        "items",
        "refundItems",
        "reqsText",
    )


def test_a_table_survives_the_json_staging_writes(tmp_path: Path) -> None:
    table = _table()
    staged = tmp_path / "Overloaded.json"
    staged.write_text(
        json.dumps(table.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    reloaded = EnumTable.model_validate(json.loads(staged.read_text(encoding="utf-8")))
    assert reloaded == table


def test_an_enum_whose_overloads_cannot_be_told_apart_is_refused() -> None:
    anchor = "\tOverloaded(int objectId, boolean"
    clash = "\tOverloaded(int width, int height, int depth, int weight) {\n\t}\n\n"
    source = _fixture().replace(anchor, clash + anchor)
    with pytest.raises(AmbiguousConstructor) as raised:
        read_enum(source, ENUM, FILENAME)
    assert raised.value.constant == "BASIC_WINDOW"
    assert raised.value.found == 4
