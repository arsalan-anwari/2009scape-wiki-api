"""Read the staged price snapshots into the price history the artifact carries."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any, Final

from wiki_api.config import PRICES_DIRNAME
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.prices import PricePoint, PriceSummary, summarise
from wiki_api.domain.vocabulary import PriceConfidence, SourceKind
from wiki_api.pipeline.artifact.overlay import (
    OverlayMode,
    OverlayPrecedence,
    OverlaySource,
)
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import MalformedSourceValue
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.collectors import PRICES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from wiki_api.pipeline.sources.staged import StagedSources

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
        Skipped(
            source=PRICES_DIRNAME,
            reason=SkipReason.UNKNOWN_TARGET,
            detail=f"item:{one}",
        )
        for one in sorted(unknown)
    )
    summaries = _summaries(prices)
    return SourceOutcome(
        source=PRICES_DIRNAME,
        read=_document(staged, prices, summaries),
        skipped=skipped,
        notes=(
            f"{len(files)} weekly snapshots read",
            _counted(summaries),
        ),
    )


def _summaries(prices: Sequence[Mapping[str, Any]]) -> tuple[PriceSummary, ...]:
    by_item: dict[int, list[PricePoint]] = defaultdict(list)
    for row in prices:
        by_item[int(row["item_id"])].append(PricePoint.model_validate(row))
    summarised = (summarise(points) for _, points in sorted(by_item.items()))
    return tuple(summary for summary in summarised if summary is not None)


def _market(summary: PriceSummary) -> dict[str, Any]:
    if summary.confidence is PriceConfidence.UNTRADED:
        return {"market_confidence": summary.confidence.value}
    return {
        "market_price": summary.latest,
        "market_confidence": summary.confidence.value,
        "market_low": summary.low,
        "market_high": summary.high,
        "market_middle": summary.middle,
        "market_entries": summary.entries,
    }


def _counted(summaries: Sequence[PriceSummary]) -> str:
    tallied = Counter(summary.confidence.value for summary in summaries)
    said = ", ".join(f"{count} {name}" for name, count in sorted(tallied.items()))
    return f"{len(summaries)} items summarised ({said})"


def _rows(path: Path) -> Sequence[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise MalformedSourceValue(
            PRICES_DIRNAME, path.name, "snapshot", "not a list of rows"
        )
    return payload


def _snapshot_date(path: Path) -> date:
    try:
        return date.fromisoformat(path.name.removesuffix(SUFFIX))
    except ValueError as error:
        raise MalformedSourceValue(
            PRICES_DIRNAME, path.name, "name", "is not a date"
        ) from error


def _document(
    staged: StagedSources,
    prices: Sequence[Mapping[str, Any]],
    summaries: Sequence[PriceSummary],
) -> OverlaySource:
    versions = {
        str(entry.game_version) for entry in staged.manifest.by_collector(PRICES)
    }
    return OverlaySource.model_validate(
        {
            "origin": PRICES_DIRNAME,
            "document": {
                "schema": 1,
                "source": SourceKind.GRAND_EXCHANGE.value,
                "source_file": PRICES_DIRNAME,
                "game_version": next(iter(sorted(versions)), "unknown"),
                "precedence": OverlayPrecedence.DECODED,
                "prices": list(prices),
                "entities": [
                    {
                        "type": EntityType.ITEM.value,
                        "id": summary.item_id,
                        "mode": OverlayMode.PATCH.value,
                        "claims": False,
                        "attributes": _market(summary),
                    }
                    for summary in summaries
                ],
            },
        }
    )


# test cases


def _sources(tmp_path: Any, snapshots: dict[str, str]) -> StagedSources:
    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {f"{PRICES_DIRNAME}/{name}": payload for name, payload in snapshots.items()},
        prices=tuple(f"{PRICES_DIRNAME}/{name}" for name in snapshots),
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


def _summarised(tmp_path: Any, *values: int) -> dict[str, Any]:
    outcome = read_prices(
        _sources(
            tmp_path,
            {
                f"2024-06-{8 + day:02d}.json": (
                    f'[{{"item_id": 4587, "value": {value}}}]'
                )
                for day, value in enumerate(values)
            },
        ),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    return dict(outcome.read.document.entities[0].attributes)


def test_a_series_that_moves_reaches_the_item_as_a_market_price(
    tmp_path: Any,
) -> None:
    attributes = _summarised(tmp_path, 100, 300, 200)
    assert attributes["market_price"] == 200
    assert attributes["market_confidence"] == "traded"
    assert attributes["market_low"] == 100
    assert attributes["market_high"] == 300
    assert attributes["market_entries"] == 3


def test_a_price_that_never_moved_says_so_rather_than_looking_traded(
    tmp_path: Any,
) -> None:
    attributes = _summarised(tmp_path, 500, 500)
    assert attributes["market_price"] == 500
    assert attributes["market_confidence"] == "static"


def test_an_item_with_no_market_carries_no_price_at_all(tmp_path: Any) -> None:
    attributes = _summarised(tmp_path, 1, 1, 1)
    assert attributes == {"market_confidence": "untraded"}


def test_a_summary_patches_the_item_rather_than_defining_it(tmp_path: Any) -> None:
    outcome = read_prices(
        _sources(tmp_path, {"2024-06-08.json": '[{"item_id": 4587, "value": 106049}]'}),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    patched = outcome.read.document.entities[0]
    assert patched.mode is OverlayMode.PATCH
    assert patched.key == EntityKey(type=EntityType.ITEM, id=4587)


def test_the_build_reports_how_many_items_have_a_market(tmp_path: Any) -> None:
    outcome = read_prices(
        _sources(tmp_path, {"2024-06-08.json": '[{"item_id": 4587, "value": 500}]'}),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    assert "1 items summarised (1 static)" in outcome.notes


def test_a_market_summary_does_not_make_the_item_look_like_a_market_fact(
    tmp_path: Any,
) -> None:
    outcome = read_prices(
        _sources(tmp_path, {"2024-06-08.json": '[{"item_id": 4587, "value": 500}]'}),
        frozenset({EntityKey(type=EntityType.ITEM, id=4587)}),
    )
    assert outcome.read.document.entities[0].claims is False
