"""Read the staged shop config into shops, their stock and who runs them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import COINS, SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import (
    Skipped,
    SkipReason,
    flag,
    groups,
    numbers,
    text,
    whole,
)
from wiki_api.pipeline.sources.errors import ConflictingRecords
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

DECLARED: Final = DeclaredConfig(name="shops.json")
ID_FIELD: Final = "id"
TITLE_FIELD: Final = "title"
NPCS_FIELD: Final = "npcs"
STOCK_FIELD: Final = "stock"
CURRENCY_FIELD: Final = "currency"
STOCK_WIDTH: Final = 3
PRICE_NOTE: Final = (
    "no line carries a price: the game works one out from a value only the cache "
    "holds, so prices arrive with the cache"
)


def read_shops(
    staged: StagedSources, overridden: frozenset[EntityKey]
) -> SourceOutcome:
    """Turn every staged shop record into an entity, minus the ones an overlay owns."""
    records = staged.records(DECLARED)
    seen: dict[int, str] = {}
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in records:
        shop_id = int(str(record[ID_FIELD]))
        title = text(record.get(TITLE_FIELD)) or ""
        key = EntityKey(type=EntityType.SHOP, id=shop_id)
        first = seen.get(shop_id)
        if first is not None and key not in overridden:
            raise ConflictingRecords(DECLARED.name, str(key), first, title)
        seen[shop_id] = title
        if key in overridden:
            skipped.append(
                Skipped(
                    source=DECLARED.name, reason=SkipReason.OVERRIDDEN, detail=str(key)
                )
            )
            continue
        entities.append(
            {
                "type": EntityType.SHOP.value,
                "id": shop_id,
                "name": title,
                "source_ref": f"{DECLARED.name}#{shop_id}",
                "attributes": {
                    "general_store": flag(record.get("general_store")),
                    "high_alch": flag(record.get("high_alch")),
                    "currency": _currency(record, shop_id),
                },
            }
        )
    return SourceOutcome(
        source=DECLARED.name,
        read=_document(staged, entities=entities),
        skipped=tuple(skipped),
        notes=(f"{len(records)} records read",),
    )


def read_shop_edges(
    staged: StagedSources, known: frozenset[EntityKey], overridden: frozenset[EntityKey]
) -> SourceOutcome:
    """Turn every stock line into a sale and every named npc into the shop's staff."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in staged.records(DECLARED):
        shop_id = int(str(record[ID_FIELD]))
        shop = EntityKey(type=EntityType.SHOP, id=shop_id)
        if shop in overridden or shop not in known:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(shop),
                )
            )
            continue
        currency = _currency(record, shop_id)
        _read_staff(record, shop, known, edges, skipped)
        _read_stock(record, shop, currency, known, edges, skipped)
    return SourceOutcome(
        source=f"{DECLARED.name} lines",
        read=_document(staged, edges=edges),
        skipped=tuple(skipped),
        notes=(PRICE_NOTE,),
    )


def _read_staff(
    record: Mapping[str, Any],
    shop: EntityKey,
    known: frozenset[EntityKey],
    edges: list[dict[str, Any]],
    skipped: list[Skipped],
) -> None:
    for order, npc_id in enumerate(
        numbers(record.get(NPCS_FIELD), DECLARED.name, str(shop.id), NPCS_FIELD)
    ):
        npc = EntityKey(type=EntityType.NPC, id=npc_id)
        if npc not in known:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(npc),
                )
            )
            continue
        edges.append(
            {
                "src": str(shop),
                "rel": RelationshipType.STAFFED_BY.value,
                "dst": str(npc),
                "order_key": order,
                "source_ref": f"{DECLARED.name}#{shop.id}.{NPCS_FIELD}",
                "attributes": {},
            }
        )


def _read_stock(
    record: Mapping[str, Any],
    shop: EntityKey,
    currency: int,
    known: frozenset[EntityKey],
    edges: list[dict[str, Any]],
    skipped: list[Skipped],
) -> None:
    lines = groups(
        record.get(STOCK_FIELD), DECLARED.name, str(shop.id), STOCK_FIELD, STOCK_WIDTH
    )
    placed: set[int] = set()
    for slot, (item_id, amount, restock) in enumerate(lines):
        item = EntityKey(type=EntityType.ITEM, id=item_id)
        if item not in known or item_id in placed:
            skipped.append(
                Skipped(
                    source=DECLARED.name,
                    reason=(
                        SkipReason.ALREADY_STATED
                        if item_id in placed
                        else SkipReason.UNKNOWN_TARGET
                    ),
                    detail=str(item),
                )
            )
            continue
        placed.add(item_id)
        edges.append(
            {
                "src": str(shop),
                "rel": RelationshipType.SELLS.value,
                "dst": str(item),
                "order_key": slot,
                "source_ref": f"{DECLARED.name}#{shop.id}.{STOCK_FIELD}",
                "attributes": {
                    "stock_amount": amount,
                    "restock_rate": restock,
                    "slot": slot,
                    "currency": currency,
                },
            }
        )


def _currency(record: Mapping[str, Any], shop_id: int) -> int:
    read = whole(
        record.get(CURRENCY_FIELD), DECLARED.name, str(shop_id), CURRENCY_FIELD
    )
    return read if read is not None else COINS.id


def _document(
    staged: StagedSources,
    entities: Sequence[Mapping[str, Any]] = (),
    edges: Sequence[Mapping[str, Any]] = (),
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": DECLARED.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CONFIG.value,
                "source_file": DECLARED.name,
                "game_version": str(staged.game_version(DECLARED.staged)),
                "entities": list(entities),
                "edges": list(edges),
            },
        }
    )


# test cases


_RECORD: Final[dict[str, Any]] = {
    "id": "53",
    "title": "Crossbow Shop",
    "npcs": "4559",
    "currency": "995",
    "general_store": "false",
    "high_alch": "0",
    "stock": "{9440,10,100}-{877,20,50}",
}


def _sources(tmp_path: Any, records: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(tmp_path, {DECLARED.staged: json.dumps(records)})


def _known() -> frozenset[EntityKey]:
    return frozenset(
        {
            EntityKey(type=EntityType.SHOP, id=53),
            EntityKey(type=EntityType.NPC, id=4559),
            EntityKey(type=EntityType.ITEM, id=9440),
            EntityKey(type=EntityType.ITEM, id=877),
        }
    )


def test_a_record_becomes_a_shop_carrying_its_currency(tmp_path: Any) -> None:
    outcome = read_shops(_sources(tmp_path, [_RECORD]), frozenset())
    entity = outcome.read.document.entities[0]
    assert entity.name == "Crossbow Shop"
    assert entity.attributes["currency"] == 995
    assert entity.attributes["general_store"] is False


def test_stock_lines_become_sales_keyed_by_their_slot(tmp_path: Any) -> None:
    outcome = read_shop_edges(_sources(tmp_path, [_RECORD]), _known(), frozenset())
    sells = [
        edge
        for edge in outcome.read.document.edges
        if edge.rel is RelationshipType.SELLS
    ]
    assert [edge.dst.id for edge in sells] == [9440, 877]
    assert sells[0].attributes == {
        "stock_amount": 10,
        "restock_rate": 100,
        "slot": 0,
        "currency": 995,
    }


def test_the_named_npcs_become_the_shops_staff(tmp_path: Any) -> None:
    outcome = read_shop_edges(_sources(tmp_path, [_RECORD]), _known(), frozenset())
    staff = [
        edge
        for edge in outcome.read.document.edges
        if edge.rel is RelationshipType.STAFFED_BY
    ]
    assert [edge.dst.id for edge in staff] == [4559]


def test_a_line_pointing_at_nothing_is_dropped_and_counted(tmp_path: Any) -> None:
    record = {**_RECORD, "stock": "{9440,10,100}-{4242,1,100}", "npcs": "4559,2258"}
    outcome = read_shop_edges(_sources(tmp_path, [record]), _known(), frozenset())
    assert outcome.edges == 2
    assert outcome.skipped_by_reason() == {"unknown_target": 2}


def test_one_shop_stocking_an_item_twice_keeps_the_first_line(tmp_path: Any) -> None:
    record = {**_RECORD, "stock": "{9440,10,100}-{9440,5,100}"}
    outcome = read_shop_edges(_sources(tmp_path, [record]), _known(), frozenset())
    sells = [
        edge
        for edge in outcome.read.document.edges
        if edge.rel is RelationshipType.SELLS
    ]
    assert len(sells) == 1
    assert sells[0].attributes["stock_amount"] == 10
    assert outcome.skipped_by_reason() == {"already_stated": 1}


def test_two_shops_with_one_id_stop_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(ConflictingRecords):
        read_shops(
            _sources(tmp_path, [_RECORD, {**_RECORD, "title": "Another"}]), frozenset()
        )


def test_an_overlay_that_owns_the_shop_settles_the_conflict(tmp_path: Any) -> None:
    overridden = frozenset({EntityKey(type=EntityType.SHOP, id=53)})
    outcome = read_shops(
        _sources(tmp_path, [_RECORD, {**_RECORD, "title": "Another"}]), overridden
    )
    assert outcome.entities == 0
    edges = read_shop_edges(_sources(tmp_path, [_RECORD]), _known(), overridden)
    assert edges.edges == 0


def test_a_shop_with_no_currency_named_trades_in_coins(tmp_path: Any) -> None:
    record = {key: value for key, value in _RECORD.items() if key != "currency"}
    outcome = read_shops(_sources(tmp_path, [record]), frozenset())
    assert outcome.read.document.entities[0].attributes["currency"] == COINS.id
