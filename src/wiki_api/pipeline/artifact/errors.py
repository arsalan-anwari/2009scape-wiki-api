from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.errors import KnowledgeError

if TYPE_CHECKING:
    from wiki_api.domain.identity import EntityKey


class BuildError(KnowledgeError):
    pass


class OverlaySchemaMismatch(BuildError):
    def __init__(self, origin: str, found: int, expected: int) -> None:
        super().__init__(
            f"{origin} declares overlay schema {found}, this build reads {expected}"
        )
        self.origin = origin
        self.found = found
        self.expected = expected


class DuplicateEntity(BuildError):
    def __init__(self, key: EntityKey, first: str, second: str) -> None:
        super().__init__(
            f"{key} is defined twice at the same precedence, by {first} and {second}; "
            f"an overlay must declare which one wins"
        )
        self.key = key
        self.first = first
        self.second = second


class UnknownEntity(BuildError):
    def __init__(self, key: EntityKey, referenced_by: str) -> None:
        super().__init__(f"{referenced_by} references unknown entity {key}")
        self.key = key
        self.referenced_by = referenced_by


class DuplicateEdge(BuildError):
    def __init__(self, description: str) -> None:
        super().__init__(f"edge defined twice: {description}")
        self.description = description


class DuplicateSourceKey(BuildError):
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
    def __init__(self, key: EntityKey, origin: str, detail: str) -> None:
        super().__init__(f"{origin} defines an invalid {key}: {detail}")
        self.key = key
        self.origin = origin
        self.detail = detail


class InvalidEdge(BuildError):
    def __init__(self, origin: str, description: str, detail: str) -> None:
        super().__init__(f"{origin} defines an invalid edge {description}: {detail}")
        self.origin = origin
        self.description = description
        self.detail = detail


class AliasConflict(BuildError):
    def __init__(self, slug: str, detail: str) -> None:
        super().__init__(f"alias {slug!r} conflicts: {detail}")
        self.slug = slug
        self.detail = detail


class PatchWithoutTarget(BuildError):
    def __init__(self, key: EntityKey, origin: str) -> None:
        super().__init__(f"{origin} patches {key}, which nothing defines")
        self.key = key
        self.origin = origin


def test_build_errors_are_knowledge_errors() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    key = EntityKey(type=EntityType.ITEM, id=14422)
    errors = (
        OverlaySchemaMismatch("items.json", 2, 1),
        DuplicateEntity(key, "items.json", "placeholders.json"),
        UnknownEntity(key, "edges.json"),
        DuplicateEdge("npc:50 drops item:536"),
        AliasConflict("dragon-scimitar", "an entity already owns this slug"),
        PatchWithoutTarget(key, "corrections.json"),
    )
    assert all(isinstance(error, BuildError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_a_duplicate_entity_error_names_both_documents() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType

    error = DuplicateEntity(
        EntityKey(type=EntityType.ITEM, id=14422),
        "item_configs.json",
        "placeholders.json",
    )
    assert "item_configs.json" in str(error)
    assert "placeholders.json" in str(error)
