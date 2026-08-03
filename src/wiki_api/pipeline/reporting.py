"""What a build read, what it left behind, and what a person should look at."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.pipeline.sources.outcome import SourceOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence

DRIFT_NOTE = "edited after staging, so it no longer matches the sources it came from"


class BuildReport(BaseModel):
    """One build, told as what each source gave and what it could not."""

    model_config = ConfigDict(frozen=True)

    data_version: str = Field(min_length=1)
    game_version: str = Field(min_length=1)
    entities: int = Field(ge=0)
    edges: int = Field(ge=0)
    prices: int = Field(ge=0)
    overlays: int = Field(ge=0)
    overridden: int = Field(ge=0)
    drifted: tuple[str, ...] = ()
    sources: tuple[SourceOutcome, ...] = ()

    @property
    def skipped(self) -> int:
        return sum(len(source.skipped) for source in self.sources)

    def lines(self) -> tuple[str, ...]:
        told = [
            f"built {self.data_version} from {self.game_version}",
            f"  {self.entities} entities, {self.edges} edges, {self.prices} prices",
            f"  {self.overlays} overlay documents, "
            f"{self.overridden} entities they own outright",
        ]
        for path in self.drifted:
            told.append(f"  {path} {DRIFT_NOTE}")
        for source in self.sources:
            told.extend(source.lines())
        if self.skipped:
            told.append(f"  {self.skipped} source rows did not become facts")
        return tuple(told)


def report_of(
    *,
    data_version: str,
    game_version: str,
    entities: int,
    edges: int,
    prices: int,
    overlays: int,
    overridden: int,
    drifted: Sequence[str],
    sources: Sequence[SourceOutcome],
) -> BuildReport:
    """Gather one build's counts into the report its command prints."""
    return BuildReport(
        data_version=data_version,
        game_version=game_version,
        entities=entities,
        edges=edges,
        prices=prices,
        overlays=overlays,
        overridden=overridden,
        drifted=tuple(drifted),
        sources=tuple(sources),
    )


# test cases


def _report(**overrides: object) -> BuildReport:
    payload: dict[str, object] = {
        "data_version": "2026.08.03",
        "game_version": "2009scape@1f4a2c9",
        "entities": 20_000,
        "edges": 60_000,
        "prices": 100,
        "overlays": 2,
        "overridden": 6,
    }
    payload.update(overrides)
    return BuildReport.model_validate(payload)


def test_a_report_leads_with_what_was_built() -> None:
    told = _report().lines()
    assert "built 2026.08.03 from 2009scape@1f4a2c9" in told[0]
    assert "20000 entities" in told[1]


def test_a_staged_file_edited_by_hand_is_named_in_the_report() -> None:
    told = "\n".join(_report(drifted=("configs/item_configs.json",)).lines())
    assert "configs/item_configs.json" in told
    assert DRIFT_NOTE in told


def test_what_the_overlays_own_is_told_so_a_stale_one_shows_up() -> None:
    told = "\n".join(_report().lines())
    assert "2 overlay documents, 6 entities they own outright" in told


def test_rows_that_did_not_become_facts_are_counted() -> None:
    from wiki_api.pipeline.artifact.overlay import OverlaySource
    from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
    from wiki_api.pipeline.sources.outcome import SourceOutcome

    outcome = SourceOutcome(
        source="drop_tables.json",
        read=OverlaySource.model_validate(
            {
                "origin": "drop_tables.json",
                "document": {
                    "schema": 1,
                    "source": "game_config",
                    "game_version": "test",
                },
            }
        ),
        skipped=(Skipped(source="drop_tables.json", reason=SkipReason.NO_CHANCE),),
    )
    report = _report(sources=(outcome,))
    assert report.skipped == 1
    assert "1 source rows did not become facts" in "\n".join(report.lines())
