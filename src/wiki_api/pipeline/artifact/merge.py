"""Fold the overlay documents into one snapshot, deterministically."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from wiki_api.domain.alias import EntityAlias
from wiki_api.domain.attributes import ATTRIBUTE_MODELS
from wiki_api.domain.entity import Entity, VariantKind, Visibility
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.prices import PricePoint
from wiki_api.domain.provenance import GameVersion, Provenance
from wiki_api.domain.relationships import Edge
from wiki_api.domain.slug import derive_slugs
from wiki_api.domain.vocabulary import HiddenReason, SourceKind
from wiki_api.pipeline.artifact.errors import (
    AliasConflict,
    DuplicateEdge,
    DuplicateEntity,
    DuplicateSourceKey,
    InvalidEdge,
    InvalidEntity,
    PatchWithoutTarget,
    UnknownEntity,
)
from wiki_api.pipeline.artifact.overlay import (
    OverlayEntity,
    OverlayMode,
    OverlaySource,
)
from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from datetime import date


@dataclass
class _Draft:
    origin: str
    precedence: int
    source: SourceKind
    game_version: GameVersion
    name: str
    source_file: str | None = None
    source_ref: str | None = None
    source_key: str | None = None
    description: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    canonical_id: int | None = None
    variant_kind: VariantKind | None = None
    visibility: Visibility | None = None
    hidden_reason: HiddenReason | None = None
    searchable: bool | None = None
    icon_ref: str | None = None


def merge(
    sources: Sequence[OverlaySource], *, strict: bool = True
) -> KnowledgeSnapshot:
    """Build a snapshot from the given documents, with later precedence winning."""
    ordered = sorted(sources, key=lambda source: source.sort_key)
    drafts = _collect_definitions(ordered)
    _apply_patches(ordered, drafts)
    entities = _build_entities(drafts)
    _check_source_keys(entities, drafts)
    by_key = {entity.key: entity for entity in entities}
    return KnowledgeSnapshot(
        entities=entities,
        edges=_build_edges(ordered, by_key),
        aliases=_build_aliases(ordered, by_key, entities),
        prices=_build_prices(ordered, by_key, strict=strict),
    )


def _collect_definitions(
    sources: Sequence[OverlaySource],
) -> dict[EntityKey, _Draft]:
    drafts: dict[EntityKey, _Draft] = {}
    for source in sources:
        document = source.document
        for overlay in document.entities:
            if overlay.mode is not OverlayMode.DEFINE:
                continue
            existing = drafts.get(overlay.key)
            if existing is not None and existing.precedence == document.precedence:
                raise DuplicateEntity(overlay.key, existing.origin, source.origin)
            drafts[overlay.key] = _Draft(
                origin=source.origin,
                precedence=document.precedence,
                source=document.source,
                game_version=document.game_version,
                name=overlay.name or "",
                source_file=document.source_file,
                source_ref=overlay.source_ref,
                source_key=overlay.source_key,
                description=overlay.description,
                attributes=dict(overlay.attributes),
                canonical_id=overlay.canonical_id,
                variant_kind=overlay.variant_kind,
                visibility=overlay.visibility,
                hidden_reason=overlay.hidden_reason,
                searchable=overlay.searchable,
                icon_ref=overlay.icon_ref,
            )
    return drafts


def _apply_patches(
    sources: Sequence[OverlaySource], drafts: dict[EntityKey, _Draft]
) -> None:
    for source in sources:
        for overlay in source.document.entities:
            if overlay.mode is not OverlayMode.PATCH:
                continue
            draft = drafts.get(overlay.key)
            if draft is None:
                raise PatchWithoutTarget(overlay.key, source.origin)
            _patch(draft, overlay, source)


def _patch(draft: _Draft, overlay: OverlayEntity, source: OverlaySource) -> None:
    draft.origin = source.origin
    draft.source = source.document.source
    draft.source_file = source.document.source_file
    draft.game_version = source.document.game_version
    if overlay.name is not None:
        draft.name = overlay.name
    if overlay.description is not None:
        draft.description = overlay.description
    if overlay.source_key is not None:
        draft.source_key = overlay.source_key
    if overlay.attributes:
        draft.attributes = {**draft.attributes, **overlay.attributes}
    if overlay.canonical_id is not None:
        draft.canonical_id = overlay.canonical_id
    if overlay.variant_kind is not None:
        draft.variant_kind = overlay.variant_kind
    if overlay.visibility is not None:
        draft.visibility = overlay.visibility
    if overlay.hidden_reason is not None:
        draft.hidden_reason = overlay.hidden_reason
    if overlay.searchable is not None:
        draft.searchable = overlay.searchable
    if overlay.icon_ref is not None:
        draft.icon_ref = overlay.icon_ref
    if overlay.source_ref is not None:
        draft.source_ref = overlay.source_ref


def _build_entities(drafts: Mapping[EntityKey, _Draft]) -> tuple[Entity, ...]:
    slugs = derive_slugs({key: draft.name for key, draft in drafts.items()})
    entities: list[Entity] = []
    for key in sorted(drafts, key=lambda key: (key.type.value, key.id)):
        draft = drafts[key]
        visibility = _visibility_of(draft)
        entities.append(_entity_of(key, draft, slugs[key], visibility))
    return tuple(entities)


def _check_source_keys(
    entities: Sequence[Entity], drafts: Mapping[EntityKey, _Draft]
) -> None:
    claimed: dict[tuple[EntityType, str], EntityKey] = {}
    for entity in entities:
        if entity.source_key is None:
            continue
        identity = (entity.key.type, entity.source_key)
        owner = claimed.get(identity)
        if owner is not None:
            raise DuplicateSourceKey(
                entity.key.type.value,
                entity.source_key,
                drafts[owner].origin,
                drafts[entity.key].origin,
            )
        claimed[identity] = entity.key


def _visibility_of(draft: _Draft) -> Visibility:
    if draft.visibility is not None:
        return draft.visibility
    if not draft.name.strip():
        return Visibility.HIDDEN
    return Visibility.PUBLISHED


def _hidden_reason_of(draft: _Draft, visibility: Visibility) -> HiddenReason | None:
    if visibility is Visibility.PUBLISHED:
        return None
    if draft.hidden_reason is not None:
        return draft.hidden_reason
    if not draft.name.strip():
        return HiddenReason.UNNAMED
    return HiddenReason.SUPPRESSED


def _searchable_of(draft: _Draft, visibility: Visibility) -> bool:
    if draft.searchable is not None:
        return draft.searchable
    return visibility is Visibility.PUBLISHED and draft.variant_kind is None


def _entity_of(
    key: EntityKey, draft: _Draft, slug: str, visibility: Visibility
) -> Entity:
    try:
        attributes = ATTRIBUTE_MODELS[key.type].model_validate(draft.attributes)
        return Entity(
            key=key,
            slug=slug,
            name=draft.name,
            description=draft.description,
            source_key=draft.source_key,
            attributes=attributes,
            canonical_id=draft.canonical_id,
            variant_kind=draft.variant_kind,
            searchable=_searchable_of(draft, visibility),
            visibility=visibility,
            hidden_reason=_hidden_reason_of(draft, visibility),
            icon_ref=draft.icon_ref,
            provenance=Provenance(
                source=draft.source,
                game_version=draft.game_version,
                source_file=draft.source_file,
                source_ref=draft.source_ref,
            ),
        )
    except ValidationError as error:
        raise InvalidEntity(key, draft.origin, _first_message(error)) from error


def _build_edges(
    sources: Sequence[OverlaySource], by_key: Mapping[EntityKey, Entity]
) -> tuple[Edge, ...]:
    edges: dict[tuple[str, int, str, str, int, str], Edge] = {}
    for source in sources:
        document = source.document
        for overlay in document.edges:
            src, dst = overlay.src, overlay.dst
            for endpoint in (src, dst):
                if endpoint not in by_key:
                    raise UnknownEntity(endpoint, source.origin)
            try:
                edge = Edge.model_validate(
                    {
                        "src": src,
                        "rel": overlay.rel,
                        "dst": dst,
                        "attributes": overlay.attributes,
                        "order_key": overlay.order_key,
                        "provenance": Provenance(
                            source=document.source,
                            game_version=document.game_version,
                            source_file=document.source_file,
                            source_ref=overlay.source_ref,
                        ),
                    }
                )
            except ValidationError as error:
                raise InvalidEdge(
                    source.origin, str(overlay), _first_message(error)
                ) from error
            identity = (
                src.type.value,
                src.id,
                overlay.rel.value,
                dst.type.value,
                dst.id,
                edge.discriminator,
            )
            if identity in edges:
                raise DuplicateEdge(str(overlay))
            edges[identity] = edge
    return tuple(edges[identity] for identity in sorted(edges))


def _build_aliases(
    sources: Sequence[OverlaySource],
    by_key: Mapping[EntityKey, Entity],
    entities: Sequence[Entity],
) -> tuple[EntityAlias, ...]:
    taken = {(entity.key.type, entity.slug) for entity in entities}
    aliases: dict[tuple[EntityType, str], EntityAlias] = {}
    for source in sources:
        for overlay in source.document.aliases:
            if overlay.key not in by_key:
                raise UnknownEntity(overlay.key, source.origin)
            identity = (overlay.type, overlay.slug)
            if identity in taken:
                raise AliasConflict(overlay.slug, "an entity already owns this slug")
            if identity in aliases:
                raise AliasConflict(overlay.slug, "declared more than once")
            aliases[identity] = EntityAlias(
                type=overlay.type,
                slug=overlay.slug,
                entity_id=overlay.id,
                kind=overlay.kind,
            )
    return tuple(
        aliases[identity]
        for identity in sorted(aliases, key=lambda key: (key[0].value, key[1]))
    )


def _build_prices(
    sources: Sequence[OverlaySource],
    by_key: Mapping[EntityKey, Entity],
    *,
    strict: bool,
) -> tuple[PricePoint, ...]:
    points: dict[tuple[int, date], PricePoint] = {}
    for source in sources:
        for overlay in source.document.prices:
            key = EntityKey(type=EntityType.ITEM, id=overlay.item_id)
            if key not in by_key:
                if strict:
                    raise UnknownEntity(key, source.origin)
                continue
            points[(overlay.item_id, overlay.snapshot_date)] = PricePoint(
                item_id=overlay.item_id,
                snapshot_date=overlay.snapshot_date,
                value=overlay.value,
            )
    return tuple(points[identity] for identity in sorted(points))


def _first_message(error: ValidationError) -> str:
    errors = error.errors()
    if not errors:
        return str(error)
    return str(errors[0].get("msg", error))


# test cases


def _source(origin: str, **overrides: Any) -> OverlaySource:
    payload: dict[str, Any] = {"schema": 1, "source": "fixture", "game_version": "test"}
    payload.update(overrides)
    return OverlaySource.model_validate({"origin": origin, "document": payload})


def _item(item_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "item", "id": item_id, "name": name}
    payload.update(overrides)
    return payload


def _npc(npc_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "npc", "id": npc_id, "name": name}
    payload.update(overrides)
    return payload


KBD = "King Black Dragon"


def test_definitions_become_entities_with_derived_slugs() -> None:
    snapshot = merge([_source("items.json", entities=[_item(4587, "Dragon scimitar")])])
    assert len(snapshot.entities) == 1
    entity = snapshot.entities[0]
    assert entity.slug == "dragon-scimitar"
    assert entity.is_published is True
    assert entity.searchable is True
    assert entity.provenance.source is SourceKind.FIXTURE


def test_a_higher_precedence_document_wins() -> None:
    snapshot = merge(
        [
            _source("items.json", entities=[_item(4587, "Dragon scimmy")]),
            _source(
                "corrections.json",
                precedence=10,
                source="overlay",
                entities=[_item(4587, "Dragon scimitar")],
            ),
        ]
    )
    assert snapshot.entities[0].name == "Dragon scimitar"
    assert snapshot.entities[0].provenance.source == "overlay"


def test_two_definitions_at_the_same_precedence_fail_the_build() -> None:
    import pytest

    with pytest.raises(DuplicateEntity):
        merge(
            [
                _source(
                    "items.json",
                    entities=[
                        _item(14422, "Sacred clay pouch (class 1)"),
                        _item(14422, "USDT Slot"),
                    ],
                )
            ]
        )


def test_an_overlay_can_declare_which_duplicate_wins() -> None:
    snapshot = merge(
        [
            _source("items.json", entities=[_item(14422, "USDT Slot")]),
            _source(
                "corrections.json",
                precedence=10,
                source="overlay",
                entities=[_item(14422, "Sacred clay pouch (class 1)")],
            ),
        ]
    )
    assert snapshot.entities[0].name == "Sacred clay pouch (class 1)"


def test_a_patch_corrects_fields_without_restating_the_entity() -> None:
    snapshot = merge(
        [
            _source(
                "items.json",
                entities=[
                    _item(
                        4587,
                        "Dragon scimitar",
                        attributes={"ge_buy_limit": 10, "tradeable": True},
                    )
                ],
            ),
            _source(
                "corrections.json",
                precedence=10,
                source="overlay",
                entities=[
                    {
                        "type": "item",
                        "id": 4587,
                        "mode": "patch",
                        "description": "A vicious, curved sword.",
                        "attributes": {"shop_price": 100000},
                    }
                ],
            ),
        ]
    )
    entity = snapshot.entities[0]
    assert entity.description == "A vicious, curved sword."
    assert entity.attributes.model_dump(exclude_none=True) == {
        "ge_buy_limit": 10,
        "tradeable": True,
        "shop_price": 100000,
    }


def test_a_patch_without_a_definition_fails_the_build() -> None:
    import pytest

    with pytest.raises(PatchWithoutTarget):
        merge(
            [
                _source(
                    "corrections.json",
                    entities=[{"type": "item", "id": 4587, "mode": "patch"}],
                )
            ]
        )


def test_an_unnamed_entity_is_hidden_and_left_out_of_search() -> None:
    snapshot = merge([_source("npcs.json", entities=[_npc(3089, "")])])
    entity = snapshot.entities[0]
    assert entity.is_published is False
    assert entity.hidden_reason is HiddenReason.UNNAMED
    assert entity.searchable is False
    assert entity.slug == "npc-3089"


def test_variants_are_never_searchable() -> None:
    snapshot = merge(
        [
            _source(
                "items.json",
                entities=[
                    _item(4587, "Dragon scimitar"),
                    _item(
                        4588,
                        "Dragon scimitar",
                        canonical_id=4587,
                        variant_kind="noted",
                    ),
                ],
            )
        ]
    )
    canonical, variant = snapshot.entities
    assert canonical.searchable is True
    assert variant.searchable is False
    assert variant.canonical_key == canonical.key


def test_invalid_attributes_name_the_entity_that_carries_them() -> None:
    import pytest

    with pytest.raises(InvalidEntity):
        merge(
            [
                _source(
                    "items.json",
                    entities=[
                        _item(
                            4587,
                            "Dragon scimitar",
                            attributes={"lifepoints": 240},
                        )
                    ],
                )
            ]
        )


def test_edges_are_built_between_existing_entities() -> None:
    snapshot = merge(
        [
            _source(
                "knowledge.json",
                entities=[
                    _npc(50, KBD),
                    _item(536, "Dragon bones"),
                ],
                edges=[
                    {
                        "src": "npc:50",
                        "rel": "drops",
                        "dst": "item:536",
                        "attributes": {
                            "weight": 100.0,
                            "denominator": 200.0,
                            "table_kind": "default",
                        },
                    }
                ],
            )
        ]
    )
    assert len(snapshot.edges) == 1
    edge = snapshot.edges[0]
    assert edge.attributes.model_dump()["denominator"] == 200.0
    assert str(edge.provenance.game_version) == "test"
    assert edge.discriminator == "default"


def test_an_edge_pointing_at_nothing_fails_the_build() -> None:
    import pytest

    with pytest.raises(UnknownEntity):
        merge(
            [
                _source(
                    "knowledge.json",
                    entities=[_npc(50, KBD)],
                    edges=[
                        {
                            "src": "npc:50",
                            "rel": "drops",
                            "dst": "item:536",
                            "attributes": {"weight": 1.0, "denominator": 2.0},
                        }
                    ],
                )
            ]
        )


def test_the_same_pair_may_be_related_twice_from_different_tables() -> None:
    snapshot = merge(
        [
            _source(
                "knowledge.json",
                entities=[
                    _npc(50, KBD),
                    _item(536, "Dragon bones"),
                ],
                edges=[
                    {
                        "src": "npc:50",
                        "rel": "drops",
                        "dst": "item:536",
                        "attributes": {
                            "weight": 1.0,
                            "denominator": 128.0,
                            "table_kind": "main",
                        },
                    },
                    {
                        "src": "npc:50",
                        "rel": "drops",
                        "dst": "item:536",
                        "attributes": {
                            "weight": 1.0,
                            "denominator": 512.0,
                            "table_kind": "tertiary",
                        },
                    },
                ],
            )
        ]
    )
    assert len(snapshot.edges) == 2
    assert {edge.discriminator for edge in snapshot.edges} == {"main", "tertiary"}


def test_the_same_edge_twice_fails_the_build() -> None:
    import pytest

    with pytest.raises(DuplicateEdge):
        merge(
            [
                _source(
                    "knowledge.json",
                    entities=[
                        _npc(50, KBD),
                        _item(536, "Dragon bones"),
                    ],
                    edges=[
                        {
                            "src": "npc:50",
                            "rel": "drops",
                            "dst": "item:536",
                            "attributes": {"weight": 1.0, "denominator": 2.0},
                        },
                        {
                            "src": "npc:50",
                            "rel": "drops",
                            "dst": "item:536",
                            "attributes": {"weight": 1.0, "denominator": 4.0},
                        },
                    ],
                )
            ]
        )


def test_an_alias_may_not_shadow_a_real_slug() -> None:
    import pytest

    with pytest.raises(AliasConflict):
        merge(
            [
                _source(
                    "items.json",
                    entities=[_item(4587, "Dragon scimitar")],
                    aliases=[{"type": "item", "slug": "dragon-scimitar", "id": 4587}],
                )
            ]
        )


def test_aliases_resolve_to_entities_that_exist() -> None:
    import pytest

    with pytest.raises(UnknownEntity):
        merge(
            [
                _source(
                    "items.json",
                    aliases=[{"type": "item", "slug": "dscim", "id": 4587}],
                )
            ]
        )


def test_prices_attach_to_items_that_exist() -> None:
    from datetime import date

    snapshot = merge(
        [
            _source(
                "items.json",
                entities=[_item(4587, "Dragon scimitar")],
                prices=[
                    {"item_id": 4587, "snapshot_date": "2024-06-15", "value": 106049},
                    {"item_id": 4587, "snapshot_date": "2024-06-08", "value": 106000},
                ],
            )
        ]
    )
    assert [point.value for point in snapshot.prices] == [106000, 106049]
    assert snapshot.prices[0].snapshot_date == date(2024, 6, 8)


def test_prices_are_ordered_by_date_rather_than_by_how_it_was_written() -> None:
    from datetime import date

    snapshot = merge(
        [
            _source(
                "items.json",
                entities=[_item(4587, "Dragon scimitar")],
                prices=[
                    {"item_id": 4587, "snapshot_date": "2024-12-07", "value": 3},
                    {"item_id": 4587, "snapshot_date": "2024-06-08", "value": 1},
                    {"item_id": 4587, "snapshot_date": "2024-09-14", "value": 2},
                ],
            )
        ]
    )
    assert [point.snapshot_date for point in snapshot.prices] == [
        date(2024, 6, 8),
        date(2024, 9, 14),
        date(2024, 12, 7),
    ]


def test_prices_for_unknown_items_are_skipped_outside_strict_mode() -> None:
    import pytest

    documents = [
        _source(
            "prices.json",
            prices=[{"item_id": 4587, "snapshot_date": "2024-06-08", "value": 1}],
        )
    ]
    with pytest.raises(UnknownEntity):
        merge(documents)
    assert merge(documents, strict=False).prices == ()


def test_the_merge_is_independent_of_document_order() -> None:
    documents = [
        _source("a.json", entities=[_item(4587, "Dragon scimitar")]),
        _source("b.json", entities=[_npc(50, KBD)]),
    ]
    forward = merge(documents)
    backward = merge(list(reversed(documents)))
    assert forward == backward


def test_entities_edges_and_prices_come_back_in_a_stable_order() -> None:
    snapshot = merge(
        [
            _source(
                "knowledge.json",
                entities=[
                    _item(536, "Dragon bones"),
                    _item(4587, "Dragon scimitar"),
                    _npc(50, KBD),
                ],
            )
        ]
    )
    assert [str(entity.key) for entity in snapshot.entities] == [
        "item:536",
        "item:4587",
        "npc:50",
    ]


def _quest(quest_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "quest", "id": quest_id, "name": name}
    payload.update(overrides)
    return payload


def test_a_type_the_source_does_not_number_carries_a_source_key() -> None:
    snapshot = merge(
        [
            _source(
                "quests.json",
                entities=[_quest(1, "Death Plateau", source_key="DEATH_PLATEAU")],
            )
        ]
    )
    assert snapshot.entities[0].source_key == "DEATH_PLATEAU"


def test_two_entities_may_not_claim_the_same_source_key() -> None:
    import pytest

    with pytest.raises(DuplicateSourceKey):
        merge(
            [
                _source(
                    "quests.json",
                    entities=[
                        _quest(1, "Death Plateau", source_key="DEATH_PLATEAU"),
                        _quest(2, "Death Plateau II", source_key="DEATH_PLATEAU"),
                    ],
                )
            ]
        )


def test_the_same_source_key_may_recur_across_types() -> None:
    snapshot = merge(
        [
            _source(
                "knowledge.json",
                entities=[
                    _quest(1, "Death Plateau", source_key="DEATH_PLATEAU"),
                    _npc(50, KBD, source_key="DEATH_PLATEAU"),
                ],
            )
        ]
    )
    assert {entity.source_key for entity in snapshot.entities} == {"DEATH_PLATEAU"}


def test_numbered_entities_leave_the_source_key_empty() -> None:
    snapshot = merge([_source("items.json", entities=[_item(4587, "Dragon scimitar")])])
    assert snapshot.entities[0].source_key is None


def test_an_overlay_can_attach_a_source_key_to_an_existing_entity() -> None:
    snapshot = merge(
        [
            _source("quests.json", entities=[_quest(1, "Death Plateau")]),
            _source(
                "corrections.json",
                precedence=10,
                source="overlay",
                entities=[
                    {
                        "type": "quest",
                        "id": 1,
                        "mode": "patch",
                        "source_key": "DEATH_PLATEAU",
                    }
                ],
            ),
        ]
    )
    assert snapshot.entities[0].source_key == "DEATH_PLATEAU"
