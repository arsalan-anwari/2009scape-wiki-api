"""The errors the knowledge layer raises."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wiki_api.domain.identity import EntityKey


class KnowledgeError(Exception):
    """Base class for everything this project raises on purpose."""

    pass


class EntityNotFound(KnowledgeError):
    """Nothing in the artifact answers to that reference."""

    def __init__(self, reference: str) -> None:
        super().__init__(f"no entity for {reference}")
        self.reference = reference


class EntityHidden(KnowledgeError):
    """The entity exists but is not published."""

    def __init__(self, key: EntityKey, reason: str | None = None) -> None:
        super().__init__(f"entity {key} is not published: {reason or 'unspecified'}")
        self.key = key
        self.reason = reason


class EntityMoved(KnowledgeError):
    """The slug was asked for by an old name and now resolves elsewhere."""

    def __init__(self, slug: str, target: EntityKey) -> None:
        super().__init__(f"slug {slug!r} now resolves to {target}")
        self.slug = slug
        self.target = target


class SlugCollision(KnowledgeError):
    """Two entities of one type wanted the same slug and disambiguating failed."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"could not derive a unique slug for {slug!r}")
        self.slug = slug


class IncompatibleArtifact(KnowledgeError):
    """The artifact was built by a schema version this runtime cannot read."""

    def __init__(self, found: int | None, expected: int) -> None:
        super().__init__(
            f"artifact schema version {found} cannot be read by this runtime, "
            f"which requires {expected}"
        )
        self.found = found
        self.expected = expected


class CorruptArtifact(KnowledgeError):
    """A stored value falls outside the vocabulary the schema declares.

    The artifact is downloaded at runtime rather than built by the process reading
    it, so a value the domain cannot name means a bad download, not a bug.
    """

    def __init__(self, table: str, column: str, value: object) -> None:
        super().__init__(f"{table}.{column} holds an unreadable value: {value!r}")
        self.table = table
        self.column = column
        self.value = value


# test cases


def test_a_corrupt_artifact_names_the_column_it_could_not_read() -> None:
    error = CorruptArtifact("entity", "type", "banana")
    assert error.column == "type"
    assert "banana" in str(error)
    assert isinstance(error, KnowledgeError)


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
