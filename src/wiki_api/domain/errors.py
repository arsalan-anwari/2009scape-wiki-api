from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wiki_api.domain.identity import EntityKey


class KnowledgeError(Exception):
    pass


class EntityNotFound(KnowledgeError):
    def __init__(self, reference: str) -> None:
        super().__init__(f"no entity for {reference}")
        self.reference = reference


class EntityHidden(KnowledgeError):
    def __init__(self, key: EntityKey, reason: str | None = None) -> None:
        super().__init__(f"entity {key} is not published: {reason or 'unspecified'}")
        self.key = key
        self.reason = reason


class EntityMoved(KnowledgeError):
    def __init__(self, slug: str, target: EntityKey) -> None:
        super().__init__(f"slug {slug!r} now resolves to {target}")
        self.slug = slug
        self.target = target


class SlugCollision(KnowledgeError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"could not derive a unique slug for {slug!r}")
        self.slug = slug


class IncompatibleArtifact(KnowledgeError):
    def __init__(self, found: int | None, expected: int) -> None:
        super().__init__(
            f"artifact schema version {found} cannot be read by this runtime, "
            f"which requires {expected}"
        )
        self.found = found
        self.expected = expected


def test_entity_moved_carries_the_redirect_target() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    target = EntityKey(type=EntityType.ITEM, id=4588)
    error = EntityMoved("dragon-scimitar-noted", target)
    assert error.target == target
    assert "dragon-scimitar-noted" in str(error)


def test_incompatible_artifact_names_both_versions() -> None:
    error = IncompatibleArtifact(found=2, expected=1)
    assert "2" in str(error)
    assert "1" in str(error)


def test_every_knowledge_error_shares_one_base() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    key = EntityKey(type=EntityType.NPC, id=50)
    errors = (
        EntityNotFound("item:1"),
        EntityHidden(key, "unnamed"),
        EntityMoved("old", key),
        SlugCollision("clue-scroll"),
        IncompatibleArtifact(None, 1),
    )
    assert all(isinstance(error, KnowledgeError) for error in errors)
