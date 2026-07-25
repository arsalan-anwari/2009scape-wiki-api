from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_api.domain.attributes import (
    ATTRIBUTE_MODELS,
    EntityAttributes,
)
from wiki_api.domain.identity import EntityKey, EntityType, Link
from wiki_api.domain.provenance import Provenance


class Visibility(StrEnum):
    PUBLISHED = "published"
    HIDDEN = "hidden"


class VariantKind(StrEnum):
    NOTED = "noted"
    BOUND = "bound"
    PLACEHOLDER = "placeholder"
    DUPLICATE = "duplicate"


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: EntityKey
    slug: str = Field(min_length=1)
    name: str
    attributes: EntityAttributes
    provenance: Provenance
    description: str | None = None
    source_key: str | None = None
    canonical_id: int | None = Field(default=None, ge=0)
    variant_kind: VariantKind | None = None
    searchable: bool = True
    visibility: Visibility = Visibility.PUBLISHED
    hidden_reason: str | None = None
    icon_ref: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_attributes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw = data.get("attributes")
        key = data.get("key")
        if not isinstance(raw, dict) or key is None:
            return data
        if isinstance(key, EntityKey):
            entity_type = key.type
        else:
            entity_type = EntityType(key["type"])
        model = ATTRIBUTE_MODELS[entity_type]
        return {**data, "attributes": model.model_validate(raw)}

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        expected = ATTRIBUTE_MODELS[self.key.type]
        if type(self.attributes) is not expected:
            raise ValueError(f"{self.key.type.value} needs {expected.__name__}")
        if self.source_key is not None and not self.source_key.strip():
            raise ValueError("a source key must not be blank")
        if (self.variant_kind is None) != (self.canonical_id is None):
            raise ValueError("a variant needs both a kind and a canonical id")
        if self.canonical_id == self.key.id:
            raise ValueError("an entity cannot be a variant of itself")
        if self.visibility is Visibility.HIDDEN and not self.hidden_reason:
            raise ValueError("a hidden entity needs a reason")
        if self.visibility is Visibility.PUBLISHED and self.hidden_reason:
            raise ValueError("a published entity cannot carry a hidden reason")
        if self.searchable and self.visibility is not Visibility.PUBLISHED:
            raise ValueError("only published entities can be searchable")
        if self.searchable and self.variant_kind is not None:
            raise ValueError("variants are never searchable")
        return self

    def __hash__(self) -> int:
        return hash(self.key)

    @property
    def type(self) -> EntityType:
        return self.key.type

    @property
    def id(self) -> int:
        return self.key.id

    @property
    def is_variant(self) -> bool:
        return self.variant_kind is not None

    @property
    def is_published(self) -> bool:
        return self.visibility is Visibility.PUBLISHED

    @property
    def canonical_key(self) -> EntityKey:
        if self.canonical_id is None:
            return self.key
        return EntityKey(type=self.key.type, id=self.canonical_id)

    def to_link(self) -> Link:
        return Link(
            type=self.key.type,
            id=self.key.id,
            slug=self.slug,
            label=self.name,
            icon_ref=self.icon_ref,
        )


def _item(**overrides: Any) -> Entity:
    payload: dict[str, Any] = {
        "key": {"type": "item", "id": 4587},
        "slug": "dragon-scimitar",
        "name": "Dragon scimitar",
        "description": "A vicious, curved sword.",
        "attributes": {"ge_buy_limit": 10, "tradeable": True},
        "provenance": {"source": "fixture", "game_version": "test"},
    }
    payload.update(overrides)
    return Entity.model_validate(payload)


def test_attributes_are_coerced_to_the_model_for_the_entity_type() -> None:
    from wiki_api.domain.attributes import ItemAttributes

    entity = _item()
    assert isinstance(entity.attributes, ItemAttributes)
    assert entity.attributes.ge_buy_limit == 10


def test_an_entity_cannot_carry_another_types_attributes() -> None:
    import pytest

    from wiki_api.domain.attributes import NpcAttributes

    with pytest.raises(ValueError):
        _item(attributes=NpcAttributes(lifepoints=240))


def test_an_empty_attribute_set_still_resolves_by_type() -> None:
    from wiki_api.domain.attributes import NpcAttributes

    entity = Entity.model_validate(
        {
            "key": {"type": "npc", "id": 3089},
            "slug": "npc-3089",
            "name": "",
            "attributes": {},
            "visibility": "hidden",
            "hidden_reason": "unnamed",
            "searchable": False,
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    assert isinstance(entity.attributes, NpcAttributes)
    assert entity.is_published is False


def test_a_variant_needs_both_a_kind_and_a_canonical_id() -> None:
    import pytest

    with pytest.raises(ValueError):
        _item(canonical_id=4587, searchable=False)
    with pytest.raises(ValueError):
        _item(variant_kind="noted", searchable=False)


def test_a_variant_points_at_its_canonical_entity_and_leaves_search() -> None:
    variant = _item(
        key={"type": "item", "id": 4588},
        slug="dragon-scimitar-4588",
        canonical_id=4587,
        variant_kind="noted",
        searchable=False,
    )
    assert variant.is_variant is True
    assert variant.canonical_key == EntityKey(type=EntityType.ITEM, id=4587)


def test_a_variant_may_not_be_searchable() -> None:
    import pytest

    with pytest.raises(ValueError):
        _item(canonical_id=4587, variant_kind="noted", searchable=True)


def test_an_entity_cannot_be_its_own_variant() -> None:
    import pytest

    with pytest.raises(ValueError):
        _item(canonical_id=4587, variant_kind="noted", searchable=False)


def test_hidden_entities_need_a_reason_and_leave_search() -> None:
    import pytest

    with pytest.raises(ValueError):
        _item(visibility="hidden", searchable=False)
    with pytest.raises(ValueError):
        _item(visibility="hidden", hidden_reason="unnamed")
    with pytest.raises(ValueError):
        _item(hidden_reason="unnamed")


def test_a_numbered_entity_needs_no_source_key() -> None:
    assert _item().source_key is None


def test_an_unnumbered_entity_carries_its_stable_source_key() -> None:
    quest = Entity.model_validate(
        {
            "key": {"type": "quest", "id": 1},
            "slug": "death-plateau",
            "name": "Death Plateau",
            "source_key": "DEATH_PLATEAU",
            "attributes": {},
            "provenance": {"source": "overlay", "game_version": "test"},
        }
    )
    assert quest.source_key == "DEATH_PLATEAU"


def test_a_blank_source_key_is_rejected() -> None:
    import pytest

    for blank in ("", "   "):
        with pytest.raises(ValueError):
            _item(source_key=blank)


def test_entities_can_be_collected_in_sets_and_dictionaries() -> None:
    entity = _item()
    same = _item()
    other = _item(key={"type": "item", "id": 536}, slug="dragon-bones")
    assert hash(entity) == hash(same)
    assert len({entity, same, other}) == 2
    assert {entity: "page"}[same] == "page"


def test_a_canonical_entity_is_its_own_canonical_key() -> None:
    entity = _item()
    assert entity.canonical_key == entity.key


def test_an_entity_renders_a_link_carrying_identity_not_a_url() -> None:
    link = _item().to_link()
    assert link.model_dump() == {
        "type": EntityType.ITEM,
        "id": 4587,
        "slug": "dragon-scimitar",
        "label": "Dragon scimitar",
        "icon_ref": None,
    }


def test_entities_are_immutable() -> None:
    import pytest

    entity = _item()
    frozen_field = "name"
    with pytest.raises(ValueError):
        setattr(entity, frozen_field, "something else")
