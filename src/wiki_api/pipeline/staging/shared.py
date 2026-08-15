"""Read one shared drop table out of the xml the game keeps beside its configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.staging.errors import SharedTableUnreadable

if TYPE_CHECKING:
    from collections.abc import Iterator

ROW_TAG: Final = "item"
ID_ATTRIBUTE: Final = "id"
WEIGHT_ATTRIBUTE: Final = "weight"
MIN_ATTRIBUTE: Final = "minAmt"
MAX_ATTRIBUTE: Final = "maxAmt"


class SharedRow(BaseModel):
    """One weighted row of a shared table."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(ge=0)
    weight: float = Field(ge=0.0)
    min_amount: int = Field(default=1, ge=0)
    max_amount: int = Field(default=1, ge=0)


class SharedTable(BaseModel):
    """One shared table, as the rows a single roll picks between."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    rows: tuple[SharedRow, ...] = ()

    @property
    def total(self) -> float:
        return sum(row.weight for row in self.rows)


def read_shared_table(source: str, name: str, origin: str) -> SharedTable:
    """Read every weighted row of one shared table, refusing a row it cannot read."""
    try:
        root = ElementTree.fromstring(source)
    except ElementTree.ParseError as error:
        raise SharedTableUnreadable(origin, str(error)) from error
    table = SharedTable(name=name, rows=tuple(_rows(root, origin)))
    if not table.rows:
        raise SharedTableUnreadable(origin, "the table states no rows")
    if table.total <= 0:
        raise SharedTableUnreadable(origin, "every row of the table weighs nothing")
    return table


def _rows(root: ElementTree.Element, origin: str) -> Iterator[SharedRow]:
    for element in root.iter(ROW_TAG):
        yield SharedRow(
            id=_whole(element, ID_ATTRIBUTE, origin),
            weight=_number(element, WEIGHT_ATTRIBUTE, origin),
            min_amount=_whole(element, MIN_ATTRIBUTE, origin),
            max_amount=_whole(element, MAX_ATTRIBUTE, origin),
        )


def _whole(element: ElementTree.Element, field: str, origin: str) -> int:
    return int(_number(element, field, origin))


def _number(element: ElementTree.Element, field: str, origin: str) -> float:
    raw = element.get(field)
    if raw is None:
        raise SharedTableUnreadable(origin, f"a row states no {field}")
    try:
        return float(raw)
    except ValueError as error:
        raise SharedTableUnreadable(origin, f"{field} reads {raw!r}") from error


# test cases

SAMPLE: Final = """
<RDT>
    <item id="995" minAmt="3000" maxAmt="3000" weight="12"/>
    <item id="1452" minAmt="1" maxAmt="1" weight="7"/>
    <item id="0" minAmt="1" maxAmt="1" weight="171"/>
</RDT>
"""


def test_a_shared_table_reads_every_weighted_row() -> None:
    table = read_shared_table(SAMPLE, "rare", "RDT.xml")
    assert table.name == "rare"
    assert [row.id for row in table.rows] == [995, 1452, 0]
    assert table.total == 190.0


def test_an_amount_range_survives_the_read() -> None:
    table = read_shared_table(SAMPLE, "rare", "RDT.xml")
    coins = table.rows[0]
    assert (coins.min_amount, coins.max_amount) == (3000, 3000)


def test_a_table_that_is_not_xml_is_refused() -> None:
    import pytest

    with pytest.raises(SharedTableUnreadable):
        read_shared_table("<RDT>", "rare", "RDT.xml")


def test_a_row_stating_no_weight_is_refused() -> None:
    import pytest

    with pytest.raises(SharedTableUnreadable):
        read_shared_table('<RDT><item id="1"/></RDT>', "rare", "RDT.xml")


def test_a_table_holding_no_rows_is_refused() -> None:
    import pytest

    with pytest.raises(SharedTableUnreadable):
        read_shared_table("<RDT></RDT>", "rare", "RDT.xml")


def test_a_table_where_nothing_can_be_rolled_is_refused() -> None:
    import pytest

    with pytest.raises(SharedTableUnreadable):
        read_shared_table('<RDT><item id="1" weight="0"/></RDT>', "rare", "RDT.xml")
