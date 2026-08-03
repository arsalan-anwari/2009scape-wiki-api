"""What one adapter produced, and what it left behind."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason

if TYPE_CHECKING:
    from collections.abc import Mapping


class SourceOutcome(BaseModel):
    """One adapter's document, together with the rows it could not carry."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    read: OverlaySource
    skipped: tuple[Skipped, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def entities(self) -> int:
        return len(self.read.document.entities)

    @property
    def edges(self) -> int:
        return len(self.read.document.edges)

    @property
    def prices(self) -> int:
        return len(self.read.document.prices)

    def skipped_by_reason(self) -> Mapping[str, int]:
        """How many rows were left behind, counted by why."""
        counted: dict[str, int] = {}
        for row in self.skipped:
            counted[row.reason.value] = counted.get(row.reason.value, 0) + 1
        return dict(sorted(counted.items()))

    def lines(self) -> tuple[str, ...]:
        told = [
            f"  {self.source}: {self.entities} entities, {self.edges} edges"
            + (f", {self.prices} prices" if self.prices else "")
        ]
        told.extend(f"    {note}" for note in self.notes)
        told.extend(
            f"    skipped {count} ({reason})"
            for reason, count in self.skipped_by_reason().items()
        )
        return tuple(told)


# test cases


def _outcome(**overrides: object) -> SourceOutcome:
    payload: dict[str, object] = {
        "source": "item_configs.json",
        "read": OverlaySource.model_validate(
            {
                "origin": "item_configs.json",
                "document": {
                    "schema": 1,
                    "source": "game_config",
                    "game_version": "test",
                    "entities": [
                        {"type": "item", "id": 4587, "name": "Dragon scimitar"}
                    ],
                },
            }
        ),
    }
    payload.update(overrides)
    return SourceOutcome.model_validate(payload)


def test_an_outcome_counts_what_it_carried() -> None:
    outcome = _outcome()
    assert outcome.entities == 1
    assert outcome.edges == 0
    assert outcome.prices == 0


def test_skipped_rows_are_counted_by_reason() -> None:
    outcome = _outcome(
        skipped=[
            Skipped(source="a", reason=SkipReason.UNKNOWN_TARGET),
            Skipped(source="a", reason=SkipReason.UNKNOWN_TARGET),
            Skipped(source="a", reason=SkipReason.NO_PLACE),
        ]
    )
    assert outcome.skipped_by_reason() == {"no_place": 1, "unknown_target": 2}


def test_an_outcome_reports_itself_in_one_line_plus_its_notes() -> None:
    outcome = _outcome(notes=("11995 records read",))
    told = "\n".join(outcome.lines())
    assert "item_configs.json: 1 entities" in told
    assert "11995 records read" in told
