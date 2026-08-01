"""Working out which entity a caller means.

Absence comes back as an answer rather than as an exception, and that answer
says whether the entity is gone, was never published, or has been renamed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import (
    Absent,
    EntityResolution,
    Found,
    Hidden,
    Missing,
    Moved,
)
from wiki_api.domain.errors import EntityHidden, EntityMoved, EntityNotFound
from wiki_api.domain.identity import EntityKey, EntityType

if TYPE_CHECKING:
    from wiki_api.domain.entity import Entity
    from wiki_api.repository.protocol import KnowledgeRepository

Reference = EntityKey | str | tuple[EntityType, str]


def resolve(repository: KnowledgeRepository, reference: Reference) -> EntityResolution:
    """Find the entity a reference names, however the caller wrote it."""
    if isinstance(reference, EntityKey):
        return _by_key(repository, reference)
    if isinstance(reference, tuple):
        entity_type, handle = reference
        return _by_handle(repository, entity_type, handle)
    return _by_text(repository, reference)


def entity_of(resolution: EntityResolution) -> Entity | None:
    """The entity a resolution found, if it found one."""
    if isinstance(resolution, Found):
        return resolution.value
    return None


def _by_key(repository: KnowledgeRepository, key: EntityKey) -> EntityResolution:
    try:
        return Found(value=repository.get_entity(key))
    except EntityHidden as hidden:
        return Hidden(key=hidden.key, reason=hidden.reason)
    except EntityNotFound:
        return Missing(reference=str(key))


def _by_text(repository: KnowledgeRepository, reference: str) -> EntityResolution:
    try:
        key = EntityKey.parse(reference)
    except ValueError:
        return Missing(reference=reference)
    return _by_key(repository, key)


def _by_handle(
    repository: KnowledgeRepository, entity_type: EntityType, handle: str
) -> EntityResolution:
    try:
        key = repository.resolve_slug(entity_type, handle)
    except EntityMoved as moved:
        return _redirect(repository, moved.target)
    except EntityNotFound:
        return _by_source_key(repository, entity_type, handle)
    return _by_key(repository, key)


def _by_source_key(
    repository: KnowledgeRepository, entity_type: EntityType, handle: str
) -> EntityResolution:
    try:
        key = repository.resolve_source_key(entity_type, handle)
    except EntityNotFound:
        return Missing(reference=f"{entity_type.value}/{handle}")
    return _by_key(repository, key)


def _redirect(repository: KnowledgeRepository, target: EntityKey) -> EntityResolution:
    """Turn a redirect into a link a reader can follow, reading the target's name so a
    caller never fetches it a second time.
    """
    found = repository.get_entities([target])
    entity = found.get(target)
    if entity is None:
        return Missing(reference=str(target))
    return Moved(target=entity.to_link())


# test cases


def test_a_reference_can_be_written_every_way_a_caller_might_write_it() -> None:
    from typing import get_args

    accepted = get_args(Reference)
    assert EntityKey in accepted
    assert str in accepted


def test_the_entity_of_an_absent_resolution_is_nothing() -> None:
    absent: tuple[Absent, ...] = (
        Missing(reference="item:1"),
        Hidden(key=EntityKey(type=EntityType.NPC, id=3089)),
    )
    for resolution in absent:
        assert entity_of(resolution) is None


def test_the_entity_of_a_found_resolution_is_the_entity() -> None:
    from wiki_api.domain.entity import Entity

    entity = Entity.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )
    assert entity_of(Found(value=entity)) is entity
