"""Name every word the registries declare, so a guard can refuse it in prose."""

from __future__ import annotations

from wiki_api.domain.attributes import ATTRIBUTE_SPECS, AttributeSpec
from wiki_api.domain.relationships import RELATIONSHIP_SPECS


def declared_names() -> set[str]:
    """Every attribute key, every part of a packed one, and every relationship."""
    names = {
        part
        for specs in ATTRIBUTE_SPECS.values()
        for spec in specs
        for part in _keys(spec)
    }
    return names | {rel.value for rel in RELATIONSHIP_SPECS}


def _keys(spec: AttributeSpec) -> set[str]:
    return {spec.key} | {part.key for part in spec.fields}
