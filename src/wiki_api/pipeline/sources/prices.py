"""Read the staged price snapshots into the price history the artifact carries."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import MalformedSourceValue
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.collectors import PRICES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from wiki_api.pipeline.sources.staged import StagedSources

SOURCE: Final = "grand-exchange"
ITEM_FIELD: Final = "item_id"
VALUE_FIELD: Final = "value"
SUFFIX: Final = ".json"


def read_prices(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Turn every staged snapshot into one price a week for the items that exist."""
    files = staged.price_files()
    prices: list[dict[str, Any]] = []
    unknown: set[int] = set()
    for path in files:
        taken = _snapshot_date(path)
        for row in _rows(path):
            item_id = int(row[ITEM_FIELD])
            if EntityKey(type=EntityType.ITEM, id=item_id) not in known:
                unknown.add(item_id)
                continue
            prices.append(
                {
                    "item_id": item_id,
                    "snapshot_date": taken.isoformat(),
                    "value": max(int(row[VALUE_FIELD]), 0),
                }
            )
    skipped = tuple(
        Skipped(source=SOURCE, reason=SkipReason.UNKNOWN_TARGET, detail=f"item:{one}")
        for one in sorted(unknown)
    )
    return SourceOutcome(
        source=SOURCE,
        read=_document(staged, prices),
        skipped=skipped,
        notes=(f"{len(files)} weekly snapshots read",),
    )


def _rows(path: Path) -> Sequence[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise MalformedSourceValue(SOURCE, path.name, "snapshot", "not a list of rows")
    return payload


def _snapshot_date(path: Path) -> date:
    try:
        return date.fromisoformat(path.name.removesuffix(SUFFIX))
    except ValueError as error:
        raise MalformedSourceValue(
            SOURCE, path.name, "name", "is not a date"
        ) from error


def _document(
    staged: StagedSources, prices: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    versions = {
        str(entry.game_version) for entry in staged.manifest.by_collector(PRICES)
    }
    return OverlaySource.model_validate(
        {
            "origin": SOURCE,
            "document": {
                "schema": 1,
                "source": SourceKind.GRAND_EXCHANGE.value,
                "source_file": SOURCE,
                "game_version": next(iter(sorted(versions)), "unknown"),
                "prices": list(prices),
            },
        }
    )


# test cases


def _sources(tmp_path: Any, snapshots: dict[str, str]) -> StagedSources:
    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {f"grand-exchange/{name}": payload for name, payload in snapshots.items()},
        prices=tuple(f"grand-exchange/{name}" for name in snapshots),
    )


def test_every_snapshot_becomes_one_price_a_week(tmp_path: Any) -> None:
    outcome = read_prices(
        _sources(
            tmp_path,
            {
                "2024-06-08.json": '[{"item_id": 4587, "value": 106049}]',
                "2026-07-25.json": '[{"item_id": 4587, "value": 108590}]',
            },
        ),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    prices = outcome.read.document.prices
    assert [price.snapshot_date for price in prices] == [
        date(2024, 6, 8),
        date(2026, 7, 25),
    ]
    assert prices[0].value == 106049


def test_a_price_for_an_item_nothing_defines_is_dropped_and_counted(
    tmp_path: Any,
) -> None:
    outcome = read_prices(
        _sources(tmp_path, {"2024-06-08.json": '[{"item_id": 42, "value": 1}]'}),
        frozenset(),
    )
    assert outcome.prices == 0
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_one_missing_item_is_counted_once_however_many_weeks_it_ran(
    tmp_path: Any,
) -> None:
    outcome = read_prices(
        _sources(
            tmp_path,
            {
                "2024-06-08.json": '[{"item_id": 42, "value": 1}]',
                "2026-07-25.json": '[{"item_id": 42, "value": 2}]',
            },
        ),
        frozenset(),
    )
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_a_negative_price_is_read_as_nothing_rather_than_refused(
    tmp_path: Any,
) -> None:
    outcome = read_prices(
        _sources(tmp_path, {"2024-06-08.json": '[{"item_id": 4587, "value": -5}]'}),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    assert outcome.read.document.prices[0].value == 0


def test_a_snapshot_that_is_not_named_after_a_day_stops_the_build(
    tmp_path: Any,
) -> None:
    import pytest

    with pytest.raises(MalformedSourceValue):
        read_prices(_sources(tmp_path, {"latest.json": "[]"}), frozenset())


def test_a_snapshot_that_is_not_a_list_stops_the_build(tmp_path: Any) -> None:
    import pytest

    with pytest.raises(MalformedSourceValue):
        read_prices(_sources(tmp_path, {"2024-06-08.json": "{}"}), frozenset())


def test_no_snapshots_read_as_no_prices(tmp_path: Any) -> None:
    outcome = read_prices(_sources(tmp_path, {}), frozenset())
    assert outcome.prices == 0
