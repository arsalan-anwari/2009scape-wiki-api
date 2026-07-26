"""What a search gives back."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.entity import Entity
from wiki_api.domain.identity import Link


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
