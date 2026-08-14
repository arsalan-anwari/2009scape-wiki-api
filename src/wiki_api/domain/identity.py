"""How an entity is identified and how one entity points at another."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

KEY_SEPARATOR = ":"


class EntityType(StrEnum):
    """The types of thing this knowledge base holds: items, NPCs, shops and more."""

    ITEM = "item"
    NPC = "npc"
    SHOP = "shop"
    QUEST = "quest"
    LOCATION = "location"
    SCENERY = "scenery"
    TASK = "task"
    ROOM = "room"
    MUSIC = "music"


class EntityKey(BaseModel):
    """What identifies an entity: its type, plus an id unique only within that type."""

    model_config = ConfigDict(frozen=True)

    type: EntityType
    id: int = Field(ge=0)

    def __hash__(self) -> int:
        return hash((self.type, self.id))

    def __str__(self) -> str:
        return f"{self.type.value}{KEY_SEPARATOR}{self.id}"

    @classmethod
    def parse(cls, value: str) -> Self:
        raw_type, separator, raw_id = value.partition(KEY_SEPARATOR)
        if not separator or not raw_id.isdigit():
            raise ValueError(f"malformed entity key: {value!r}")
        return cls(type=EntityType(raw_type), id=int(raw_id))


class Link(BaseModel):
    """A pointer to another entity, carrying `type`, `id`, `slug` and `label` but never
    a URL.
    """

    model_config = ConfigDict(frozen=True)

    type: EntityType
    id: int = Field(ge=0)
    slug: str = Field(min_length=1)
    label: str
    icon_ref: str | None = None

    @property
    def key(self) -> EntityKey:
        return EntityKey(type=self.type, id=self.id)


# test cases


def test_entity_key_round_trips_through_its_string_form() -> None:
    key = EntityKey(type=EntityType.ITEM, id=4587)
    assert str(key) == "item:4587"
    assert EntityKey.parse("item:4587") == key


def test_entity_keys_are_hashable_and_compare_by_value() -> None:
    first = EntityKey(type=EntityType.NPC, id=50)
    second = EntityKey(type=EntityType.NPC, id=50)
    assert first == second
    assert len({first, second}) == 1


def test_the_same_number_in_two_types_is_two_different_keys() -> None:
    item = EntityKey(type=EntityType.ITEM, id=50)
    npc = EntityKey(type=EntityType.NPC, id=50)
    assert item != npc
    assert len({item, npc}) == 2


def test_malformed_entity_keys_are_rejected() -> None:
    import pytest

    for value in ("4587", "item:", "item:abc", ":4587", "spell:1"):
        with pytest.raises(ValueError):
            EntityKey.parse(value)


def test_link_exposes_the_key_it_points_at() -> None:
    link = Link(
        type=EntityType.ITEM,
        id=4587,
        slug="dragon-scimitar",
        label="Dragon scimitar",
    )
    assert link.key == EntityKey(type=EntityType.ITEM, id=4587)
    assert link.icon_ref is None
