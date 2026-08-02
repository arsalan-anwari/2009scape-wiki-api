from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tests.artifact import FIXTURE_KNOWLEDGE
from wiki_api.domain.alias import AliasKind
from wiki_api.domain.attributes import ATTRIBUTE_SPECS
from wiki_api.domain.entity import Visibility
from wiki_api.domain.identity import EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.pipeline.artifact import OVERLAY_SCHEMA, load_documents

if TYPE_CHECKING:
    from wiki_api.pipeline.artifact import KnowledgeSnapshot


def test_the_fixtures_cover_every_entity_type(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    covered = {entity.key.type for entity in fixture_snapshot.entities}
    assert covered == set(EntityType)


def test_the_fixtures_cover_every_relationship_type(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    covered = {edge.rel for edge in fixture_snapshot.edges}
    assert covered == set(RelationshipType)


def test_the_fixtures_cover_a_canonical_variant_pair(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    variants = [entity for entity in fixture_snapshot.entities if entity.is_variant]
    assert variants
    canonical_keys = {entity.canonical_key for entity in variants}
    assert canonical_keys <= set(fixture_snapshot.keys)
    assert all(variant.searchable is False for variant in variants)


def test_the_fixtures_cover_a_hidden_entity(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    hidden = [
        entity
        for entity in fixture_snapshot.entities
        if entity.visibility is Visibility.HIDDEN
    ]
    assert hidden
    assert all(entity.hidden_reason for entity in hidden)


def test_the_fixtures_cover_both_alias_purposes(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    kinds = {alias.kind for alias in fixture_snapshot.aliases}
    assert AliasKind.RETIRED_SLUG in kinds
    assert AliasKind.SHORTHAND in kinds


def test_the_fixtures_cover_a_hand_authored_entity(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    authored = [
        entity
        for entity in fixture_snapshot.entities
        if entity.provenance.source == "overlay"
    ]
    assert {entity.key.type for entity in authored} >= {EntityType.QUEST}


def test_the_fixtures_cover_a_drop_rate_and_a_shop_price(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    from wiki_api.domain.relationships import DropEdgeAttributes, SellEdgeAttributes

    drops = [
        edge.attributes
        for edge in fixture_snapshot.edges
        if isinstance(edge.attributes, DropEdgeAttributes)
    ]
    assert any(attributes.one_in == 128.0 for attributes in drops)
    sells = [
        edge.attributes
        for edge in fixture_snapshot.edges
        if isinstance(edge.attributes, SellEdgeAttributes)
    ]
    assert any(attributes.price is not None for attributes in sells)


def test_the_fixtures_cover_a_price_series(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    by_item: dict[int, int] = {}
    for point in fixture_snapshot.prices:
        by_item[point.item_id] = by_item.get(point.item_id, 0) + 1
    assert max(by_item.values()) >= 3


def test_every_slug_is_unique_within_its_type(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    slugs = [(entity.key.type, entity.slug) for entity in fixture_snapshot.entities]
    assert len(slugs) == len(set(slugs))


def test_no_alias_shadows_a_real_slug(fixture_snapshot: KnowledgeSnapshot) -> None:
    slugs = {(entity.key.type, entity.slug) for entity in fixture_snapshot.entities}
    aliases = {(alias.type, alias.slug) for alias in fixture_snapshot.aliases}
    assert not slugs & aliases


def test_every_attribute_in_the_fixtures_is_declared_in_the_registry(
    fixture_snapshot: KnowledgeSnapshot,
) -> None:
    for entity in fixture_snapshot.entities:
        declared = {spec.key for spec in ATTRIBUTE_SPECS[entity.key.type]}
        used = set(entity.attributes.model_dump(exclude_none=True))
        assert used <= declared


def test_every_fixture_document_declares_the_current_overlay_schema() -> None:
    sources = load_documents(FIXTURE_KNOWLEDGE)
    assert sources
    for source in sources:
        assert source.document.schema_version == OVERLAY_SCHEMA
        assert source.document.source
        assert source.document.game_version


def test_the_fixture_documents_are_valid_json_on_disk() -> None:
    paths = sorted(FIXTURE_KNOWLEDGE.glob("*.json"))
    assert len(paths) >= 5
    for path in paths:
        assert json.loads(path.read_text(encoding="utf-8"))


def test_the_fixtures_exercise_the_duplicate_id_policy() -> None:
    sources = load_documents(FIXTURE_KNOWLEDGE)
    defined: dict[tuple[str, int], list[int]] = {}
    for source in sources:
        for entity in source.document.entities:
            key = (entity.type.value, entity.id)
            defined.setdefault(key, []).append(source.document.precedence)
    contested = {key: levels for key, levels in defined.items() if len(levels) > 1}
    assert contested
    for levels in contested.values():
        assert len(set(levels)) == len(levels)
