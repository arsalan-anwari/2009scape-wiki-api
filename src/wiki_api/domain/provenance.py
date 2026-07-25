from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

FIXTURE_SOURCE: Final = "fixture"
OVERLAY_SOURCE: Final = "overlay"


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    game_version: str = Field(min_length=1)
    source_ref: str | None = None


def test_provenance_records_where_a_fact_came_from() -> None:
    provenance = Provenance(
        source="item_configs.json",
        game_version="2009scape@1f4a2c9",
        source_ref="item:4587",
    )
    assert provenance.source_ref == "item:4587"


def test_a_source_and_game_version_are_mandatory() -> None:
    import pytest

    with pytest.raises(ValueError):
        Provenance(source="", game_version="x")
    with pytest.raises(ValueError):
        Provenance(source="x", game_version="")
