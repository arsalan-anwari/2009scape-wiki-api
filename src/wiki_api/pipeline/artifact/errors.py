"""Errors a build raises, each naming the document at fault."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.errors import KnowledgeError

if TYPE_CHECKING:
    from wiki_api.domain.identity import EntityKey


class BuildError(KnowledgeError):
    """Base class for anything that stops a build."""

    pass


class OverlaySchemaMismatch(BuildError):
    """The document was written for a different overlay schema than this build reads."""

    def __init__(self, origin: str, found: int, expected: int) -> None:
        super().__init__(
            f"{origin} declares overlay schema {found}, this build reads {expected}"
        )
        self.origin = origin
        self.found = found
        self.expected = expected


class InvalidOverlayDocument(BuildError):
    """A document the overlay models reject on load, carrying the filename and the
    offending field.
    """

    def __init__(self, origin: str, detail: str) -> None:
        super().__init__(f"{origin} is not a readable overlay: {detail}")
        self.origin = origin
        self.detail = detail


class DuplicateEntity(BuildError):
    """Two documents at the same precedence both define one entity."""

    def __init__(self, key: EntityKey, first: str, second: str) -> None:
        super().__init__(
            f"{key} is defined twice at the same precedence, by {first} and {second}; "
            f"an overlay must declare which one wins"
        )
        self.key = key
        self.first = first
        self.second = second


class UnknownEntity(BuildError):
    """A document points at an entity that nothing defines."""

    def __init__(self, key: EntityKey, referenced_by: str) -> None:
        super().__init__(f"{referenced_by} references unknown entity {key}")
        self.key = key
        self.referenced_by = referenced_by


class VariantChain(BuildError):
    """A variant points at an entity that is itself a variant."""

    def __init__(self, key: EntityKey, canonical: EntityKey, origin: str) -> None:
        super().__init__(
            f"{origin} makes {key} a variant of {canonical}, which is itself a "
            f"variant; a variant points at the entity a walk collapses onto"
        )
        self.key = key
        self.canonical = canonical
        self.origin = origin


class OverlayExpired(BuildError):
    """A correction states what the source said, and the source no longer says it."""

    def __init__(
        self, key: EntityKey, origin: str, field: str, expected: object, found: object
    ) -> None:
        super().__init__(
            f"{origin} corrects {key} expecting {field} to be {expected!r}, and the "
            f"source now says {found!r}; check the correction is still needed"
        )
        self.key = key
        self.origin = origin
        self.field = field
        self.expected = expected
        self.found = found


class DuplicateEdge(BuildError):
    """One relationship between one pair is declared twice."""

    def __init__(self, description: str) -> None:
        super().__init__(f"edge defined twice: {description}")
        self.description = description


class DuplicateSourceKey(BuildError):
    """Two entities of one type claim the same stable key from the sources."""

    def __init__(
        self, entity_type: str, source_key: str, first: str, second: str
    ) -> None:
        super().__init__(
            f"two {entity_type} entities claim source key {source_key!r} "
            f"({first} and {second}); one thing must have one identity"
        )
        self.entity_type = entity_type
        self.source_key = source_key
        self.first = first
        self.second = second


class InvalidEntity(BuildError):
    """A document defines an entity the domain rejects."""

    def __init__(self, key: EntityKey, origin: str, detail: str) -> None:
        super().__init__(f"{origin} defines an invalid {key}: {detail}")
        self.key = key
        self.origin = origin
        self.detail = detail


class InvalidEdge(BuildError):
    """A document defines a relationship the domain rejects."""

    def __init__(self, origin: str, description: str, detail: str) -> None:
        super().__init__(f"{origin} defines an invalid edge {description}: {detail}")
        self.origin = origin
        self.description = description
        self.detail = detail


class AliasConflict(BuildError):
    """An alias collides with a real slug or with another alias."""

    def __init__(self, slug: str, detail: str) -> None:
        super().__init__(f"alias {slug!r} conflicts: {detail}")
        self.slug = slug
        self.detail = detail


class PatchWithoutTarget(BuildError):
    """A document corrects an entity that nothing defines."""

    def __init__(self, key: EntityKey, origin: str) -> None:
        super().__init__(f"{origin} patches {key}, which nothing defines")
        self.key = key
        self.origin = origin


# test cases


def test_build_errors_are_knowledge_errors() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    key = EntityKey(type=EntityType.ITEM, id=14422)
    errors = (
        OverlaySchemaMismatch("items.json", 2, 1),
        InvalidOverlayDocument("items.json", "edges.0.src: malformed entity key"),
        DuplicateEntity(key, "items.json", "placeholders.json"),
        UnknownEntity(key, "edges.json"),
        VariantChain(key, EntityKey(type=EntityType.ITEM, id=4587), "items.json"),
        DuplicateEdge("npc:50 drops item:536"),
        AliasConflict("dragon-scimitar", "an entity already owns this slug"),
        PatchWithoutTarget(key, "corrections.json"),
    )
    assert all(isinstance(error, BuildError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_a_variant_chain_error_names_both_ends() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    error = VariantChain(
        EntityKey(type=EntityType.ITEM, id=13477),
        EntityKey(type=EntityType.ITEM, id=4588),
        "cache/items.json",
    )
    assert "item:13477" in str(error)
    assert "item:4588" in str(error)


def test_a_duplicate_entity_error_names_both_documents() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    error = DuplicateEntity(
        EntityKey(type=EntityType.ITEM, id=14422),
        "item_configs.json",
        "placeholders.json",
    )
    assert "item_configs.json" in str(error)
    assert "placeholders.json" in str(error)
