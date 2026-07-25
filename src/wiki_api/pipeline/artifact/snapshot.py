from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from wiki_api.domain.alias import EntityAlias
from wiki_api.domain.entity import Entity
from wiki_api.domain.identity import EntityKey
from wiki_api.domain.prices import PricePoint
from wiki_api.domain.relationships import Edge


class KnowledgeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    entities: tuple[Entity, ...] = ()
    edges: tuple[Edge, ...] = ()
    aliases: tuple[EntityAlias, ...] = ()
    prices: tuple[PricePoint, ...] = ()

    @property
    def keys(self) -> tuple[EntityKey, ...]:
        return tuple(entity.key for entity in self.entities)


def test_an_empty_snapshot_is_valid() -> None:
    snapshot = KnowledgeSnapshot()
    assert snapshot.entities == ()
    assert snapshot.keys == ()


def test_a_snapshot_lists_the_keys_it_holds() -> None:
    entity = Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    snapshot = KnowledgeSnapshot(entities=(entity,))
    assert snapshot.keys == (entity.key,)
