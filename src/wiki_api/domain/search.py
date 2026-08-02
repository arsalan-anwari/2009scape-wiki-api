"""What a search gives back, and how close a near miss has to be to be worth
offering.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.entity import Entity
from wiki_api.domain.identity import Link

NEAR_LIMIT: Final = 5
NEAR_KEEP: Final = 0.9
NEAR_FLOOR: Final = 0.6
MOST_NEAR_LIMIT: Final = 25


class SearchHit(BaseModel):
    """One entity a search matched, with the score it matched at."""

    model_config = ConfigDict(frozen=True)

    entity: Entity
    score: float = Field(ge=0.0)

    @property
    def link(self) -> Link:
        return self.entity.to_link()


# test cases


def test_a_hit_carries_the_entity_and_a_non_negative_score() -> None:
    entity = Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    hit = SearchHit(entity=entity, score=12.5)
    assert hit.entity.name == "Dragon scimitar"
    assert hit.score == 12.5


def test_a_near_miss_is_only_offered_when_it_is_actually_close() -> None:
    assert 0.0 < NEAR_FLOOR < 1.0
    assert 0.0 < NEAR_KEEP <= 1.0


def test_only_a_handful_of_near_misses_are_ever_offered() -> None:
    assert 1 <= NEAR_LIMIT <= MOST_NEAR_LIMIT


def test_negative_scores_are_rejected() -> None:
    import pytest

    entity = Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    with pytest.raises(ValueError):
        SearchHit(entity=entity, score=-1.0)
