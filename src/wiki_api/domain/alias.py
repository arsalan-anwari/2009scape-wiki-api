"""Alternate slugs that redirect to an entity so old links keep working."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from wiki_api.domain.identity import EntityKey, EntityType


class AliasKind(StrEnum):
    """Why an alias exists."""

    RETIRED_SLUG = "retired_slug"
    SHORTHAND = "shorthand"
    ALTERNATE_NAME = "alternate_name"


class EntityAlias(BaseModel):
    """A slug that resolves to an entity it is not the main name for."""

    model_config = ConfigDict(frozen=True)

    type: EntityType
    slug: str = Field(min_length=1)
    entity_id: int = Field(ge=0)
    kind: AliasKind

    @property
    def key(self) -> EntityKey:
        return EntityKey(type=self.type, id=self.entity_id)


# test cases


def test_an_alias_points_at_the_entity_that_replaced_it() -> None:
    alias = EntityAlias(
        type=EntityType.ITEM,
        slug="dragon-scimitar-noted",
        entity_id=4588,
        kind=AliasKind.ALTERNATE_NAME,
    )
    assert alias.key == EntityKey(type=EntityType.ITEM, id=4588)


def test_shorthand_and_retired_slugs_are_both_aliases() -> None:
    kinds = {kind.value for kind in AliasKind}
    assert kinds == {"retired_slug", "shorthand", "alternate_name"}


def test_an_alias_needs_a_slug() -> None:
    import pytest

    with pytest.raises(ValueError):
        EntityAlias(
            type=EntityType.ITEM,
            slug="",
            entity_id=4588,
            kind=AliasKind.SHORTHAND,
        )
