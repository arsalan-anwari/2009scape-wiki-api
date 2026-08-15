"""Fold the overlay documents into one snapshot, deterministically."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from pydantic import ValidationError

from wiki_api.domain.alias import EntityAlias
from wiki_api.domain.attributes import ATTRIBUTE_MODELS, ATTRIBUTE_SPECS
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
    OverlayExpired,
    PatchWithoutTarget,
    UnknownEntity,
    VariantChain,
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
    source_revision: str | None = None
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
    _fold_namesakes(drafts)
    entities = _build_entities(drafts)
    _check_source_keys(entities, drafts)
    by_key = {entity.key: entity for entity in entities}
    _check_canonical(entities, drafts, by_key)
    return KnowledgeSnapshot(
        entities=entities,
        edges=_fold_edges(_build_edges(ordered, by_key), by_key),
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
                source_revision=document.source_revision,
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
            if overlay.expects is not None:
                _check_expectation(draft, overlay, source.origin)
            _patch(draft, overlay, source)


def _check_expectation(draft: _Draft, overlay: OverlayEntity, origin: str) -> None:
    expected = overlay.expects
    if expected is None:
        return
    stated: list[tuple[str, Any, Any]] = []
    if expected.name is not None:
        stated.append(("name", expected.name, draft.name))
    if expected.description is not None:
        stated.append(("description", expected.description, draft.description))
    stated.extend(
        (key, value, draft.attributes.get(key))
        for key, value in expected.attributes.items()
    )
    for stated_field, wanted, found in stated:
        if wanted != found:
            raise OverlayExpired(overlay.key, origin, stated_field, wanted, found)


def _patch(draft: _Draft, overlay: OverlayEntity, source: OverlaySource) -> None:
    if overlay.claims:
        draft.origin = source.origin
        draft.source = source.document.source
        draft.source_file = source.document.source_file
        draft.source_revision = source.document.source_revision
        draft.game_version = source.document.game_version
        if overlay.source_ref is not None:
            draft.source_ref = overlay.source_ref
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


def _fold_namesakes(drafts: dict[EntityKey, _Draft]) -> None:
    """Leave one record standing for each name a sort of thing answers to, and make
    every other one a copy of it."""
    moved: dict[EntityKey, int] = {}
    for group in _by_name(drafts).values():
        if len(group) < 2:
            continue
        standing, *copies = group
        _total_onto(drafts[standing], [drafts[key] for key in copies])
        for key in copies:
            drafts[key].canonical_id = standing.id
            drafts[key].variant_kind = VariantKind.DUPLICATE
            moved[key] = standing.id
    _repoint(drafts, moved)


def _repoint(
    drafts: Mapping[EntityKey, _Draft], moved: Mapping[EntityKey, int]
) -> None:
    """Send every copy the sources already declared to the record still standing."""
    for key, draft in drafts.items():
        if draft.canonical_id is None or key in moved:
            continue
        standing = moved.get(EntityKey(type=key.type, id=draft.canonical_id))
        if standing is not None:
            draft.canonical_id = standing


def _by_name(
    drafts: Mapping[EntityKey, _Draft],
) -> dict[tuple[str, str], list[EntityKey]]:
    """Every publishable record grouped under the name it answers to, richest first."""
    copied = _already_copied(drafts)
    found: dict[tuple[str, str], list[EntityKey]] = {}
    for key in sorted(drafts, key=lambda key: (key.type.value, key.id)):
        draft = drafts[key]
        if _is_copy(draft) or _visibility_of(draft) is not Visibility.PUBLISHED:
            continue
        found.setdefault((key.type.value, draft.name.casefold()), []).append(key)
    return {
        name: sorted(
            keys,
            key=lambda key: (key not in copied, -_recorded(drafts[key]), key.id),
        )
        for name, keys in found.items()
    }


def _already_copied(drafts: Mapping[EntityKey, _Draft]) -> frozenset[EntityKey]:
    """Every record the sources already point a copy at."""
    return frozenset(
        EntityKey(type=key.type, id=draft.canonical_id)
        for key, draft in drafts.items()
        if draft.canonical_id is not None
    )


def _recorded(draft: _Draft) -> int:
    """How much one record actually says, counting a value it leaves empty as
    nothing said.
    """
    said = sum(1 for value in draft.attributes.values() if value not in (None, [], ""))
    return said + bool(draft.description)


def _total_onto(standing: _Draft, copies: Sequence[_Draft]) -> None:
    """Add every count of the world the copies hold onto the record that stays."""
    for key in _TOTALLED:
        counted = [_count(draft.attributes.get(key)) for draft in (standing, *copies)]
        if any(number is not None for number in counted):
            standing.attributes[key] = sum(
                number for number in counted if number is not None
            )


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _totalled_keys() -> frozenset[str]:
    return frozenset(
        spec.key
        for specs in ATTRIBUTE_SPECS.values()
        for spec in specs
        if spec.totalled
    )


_TOTALLED: Final = _totalled_keys()


def _build_entities(drafts: Mapping[EntityKey, _Draft]) -> tuple[Entity, ...]:
    slugs = derive_slugs(
        {key: draft.name for key, draft in drafts.items()},
        variants={key for key, draft in drafts.items() if _is_copy(draft)},
    )
    entities: list[Entity] = []
    for key in sorted(drafts, key=lambda key: (key.type.value, key.id)):
        draft = drafts[key]
        visibility = _visibility_of(draft)
        entities.append(_entity_of(key, draft, slugs[key], visibility))
    return tuple(entities)


def _is_copy(draft: _Draft) -> bool:
    return draft.canonical_id is not None


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


def _check_canonical(
    entities: Sequence[Entity],
    drafts: Mapping[EntityKey, _Draft],
    by_key: Mapping[EntityKey, Entity],
) -> None:
    for entity in entities:
        if entity.canonical_id is None:
            continue
        origin = drafts[entity.key].origin
        canonical = by_key.get(entity.canonical_key)
        if canonical is None:
            raise UnknownEntity(entity.canonical_key, origin)
        if canonical.is_variant:
            raise VariantChain(entity.key, canonical.key, origin)


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
                source_revision=draft.source_revision,
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
                            source_revision=document.source_revision,
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


def _fold_edges(
    edges: Sequence[Edge], by_key: Mapping[EntityKey, Entity]
) -> tuple[Edge, ...]:
    """Move every link that ends on a copy onto the record its name stands behind, and
    keep one of any two that land on top of each other."""
    folded: dict[tuple[str, int, str, str, int, str], tuple[int, Edge]] = {}
    for edge in edges:
        src = _standing(edge.src, by_key)
        dst = _standing(edge.dst, by_key)
        written = (src, dst) == (edge.src, edge.dst)
        if not written and src == dst:
            continue
        identity = (
            src.type.value,
            src.id,
            edge.rel.value,
            dst.type.value,
            dst.id,
            edge.discriminator,
        )
        rank = 0 if written else 1
        held = folded.get(identity)
        if held is None or rank < held[0]:
            folded[identity] = (rank, edge if written else _moved(edge, src, dst))
    return tuple(folded[identity][1] for identity in sorted(folded))


def _standing(key: EntityKey, by_key: Mapping[EntityKey, Entity]) -> EntityKey:
    """The record one key answers for, which is itself unless it is a
    copy of another."""
    entity = by_key.get(key)
    if entity is None or entity.variant_kind is None:
        return key
    return entity.canonical_key


def _moved(edge: Edge, src: EntityKey, dst: EntityKey) -> Edge:
    return edge.model_copy(update={"src": src, "dst": dst})


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


def _claimed(claims: bool) -> Entity:
    snapshot = merge(
        [
            _source(
                "items.json",
                source="game_config",
                entities=[_item(4587, "Dragon scimitar")],
            ),
            _source(
                "grand-exchange",
                precedence=1,
                source="grand_exchange",
                entities=[
                    {
                        "type": "item",
                        "id": 4587,
                        "mode": "patch",
                        "claims": claims,
                        "attributes": {"market_price": 108590},
                    }
                ],
            ),
        ]
    )
    return snapshot.entities[0]


def test_a_patch_that_declines_the_entity_leaves_its_source_alone() -> None:
    entity = _claimed(claims=False)
    assert entity.provenance.source is SourceKind.GAME_CONFIG
    assert entity.attributes.model_dump(exclude_none=True) == {"market_price": 108590}


def test_a_patch_that_claims_the_entity_takes_its_source_over() -> None:
    entity = _claimed(claims=True)
    assert entity.provenance.source is SourceKind.GRAND_EXCHANGE


def test_only_a_patch_may_decline_the_entity_it_writes() -> None:
    import pytest

    from wiki_api.pipeline.artifact.overlay import OverlayEntity

    with pytest.raises(ValueError, match="does not claim"):
        OverlayEntity.model_validate(
            {"type": "item", "id": 4587, "name": "Dragon scimitar", "claims": False}
        )


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


def test_a_decoded_fact_carries_the_revision_its_document_names() -> None:
    snapshot = merge(
        [
            _source(
                "cache/items.json",
                source="game_cache",
                source_revision="index 19 revision 214",
                entities=[_item(4587, "Dragon scimitar")],
            )
        ]
    )
    assert snapshot.entities[0].provenance.source_revision == "index 19 revision 214"


def test_a_variant_gives_the_bare_slug_to_the_entity_it_copies() -> None:
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
    slugs = {entity.key.id: entity.slug for entity in snapshot.entities}
    assert slugs == {4587: "dragon-scimitar", 4588: "dragon-scimitar-4588"}


def _corrected(expects: dict[str, Any], **source: Any) -> list[OverlaySource]:
    return [
        _source(
            "items.json",
            entities=[
                _item(4587, "Dragon scimitar", attributes={"ge_buy_limit": 10}),
            ],
            **source,
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
                    "attributes": {"ge_buy_limit": 20},
                    "expects": expects,
                }
            ],
        ),
    ]


def test_a_correction_that_still_matches_the_source_applies() -> None:
    snapshot = merge(_corrected({"attributes": {"ge_buy_limit": 10}}))
    assert snapshot.entities[0].attributes.model_dump(exclude_none=True) == {
        "ge_buy_limit": 20
    }


def test_a_correction_fails_once_the_source_says_something_else() -> None:
    import pytest

    with pytest.raises(OverlayExpired) as caught:
        merge(_corrected({"attributes": {"ge_buy_limit": 99}}))
    assert caught.value.field == "ge_buy_limit"
    assert caught.value.expected == 99
    assert caught.value.found == 10


def test_a_correction_can_state_what_the_source_called_the_entity() -> None:
    import pytest

    with pytest.raises(OverlayExpired) as caught:
        merge(_corrected({"name": "Dragon scimmy"}))
    assert caught.value.field == "name"


def test_a_correction_can_state_that_the_source_says_nothing_at_all() -> None:
    import pytest

    merge(_corrected({"attributes": {"weight": None}}))
    with pytest.raises(OverlayExpired):
        merge(_corrected({"attributes": {"ge_buy_limit": None}}))


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


def test_a_variant_of_an_item_nothing_defines_fails_the_build() -> None:
    import pytest

    with pytest.raises(UnknownEntity):
        merge(
            [
                _source(
                    "items.json",
                    entities=[
                        _item(
                            4588,
                            "Dragon scimitar",
                            canonical_id=4587,
                            variant_kind="noted",
                        )
                    ],
                )
            ]
        )


def test_a_variant_may_not_point_at_another_variant() -> None:
    import pytest

    with pytest.raises(VariantChain):
        merge(
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
                        _item(
                            13477,
                            "Dragon scimitar",
                            canonical_id=4588,
                            variant_kind="bound",
                        ),
                    ],
                )
            ]
        )


def test_a_patch_that_collapses_onto_nothing_fails_the_build() -> None:
    import pytest

    with pytest.raises(UnknownEntity):
        merge(
            [
                _source("items.json", entities=[_item(4588, "Dragon scimitar")]),
                _source(
                    "cache/items.json",
                    precedence=1,
                    source="game_cache",
                    entities=[
                        {
                            "type": "item",
                            "id": 4588,
                            "mode": "patch",
                            "canonical_id": 4587,
                            "variant_kind": "noted",
                            "searchable": False,
                        }
                    ],
                ),
            ]
        )


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


def _scenery(scenery_id: int, name: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "scenery", "id": scenery_id, "name": name}
    payload.update(overrides)
    return payload


def test_one_name_a_sort_of_thing_answers_to_leaves_one_record_standing() -> None:
    """Eighteen records answer to `Tormented demon`, and a reader can tell them apart
    only by numbers it is never allowed to say.
    """
    snapshot = merge(
        [
            _source(
                "npcs.json",
                entities=[_npc(number, "Tormented demon") for number in (8349, 8350)],
            )
        ]
    )
    standing = [entity for entity in snapshot.entities if not entity.is_variant]
    assert [entity.key.id for entity in standing] == [8349]
    copied = [entity for entity in snapshot.entities if entity.is_variant]
    assert copied[0].canonical_key == standing[0].key
    assert copied[0].variant_kind is VariantKind.DUPLICATE
    assert copied[0].searchable is False


def test_the_record_that_says_the_most_is_the_one_the_name_keeps() -> None:
    """Of three fishing spots, the one that says what it is beats the one that says
    only that it is there, whatever order their numbers fall in.
    """
    snapshot = merge(
        [
            _source(
                "scenery.json",
                entities=[
                    _scenery(2026, "Fishing spot"),
                    _scenery(
                        8986,
                        "Fishing spot",
                        description="I can see fish swimming in the water.",
                        attributes={"options": ["Net", "Bait"]},
                    ),
                    _scenery(14428, "Fishing spot"),
                ],
            )
        ]
    )
    standing = [entity for entity in snapshot.entities if not entity.is_variant]
    assert [entity.key.id for entity in standing] == [8986]


def test_a_count_of_the_world_adds_up_over_everything_folded_onto_one_name() -> None:
    """Sixteen booths stand under the number the fold keeps and fifty stand in the
    world, and the answer has to be fifty.
    """
    from wiki_api.domain.attributes import SceneryAttributes

    snapshot = merge(
        [
            _source(
                "scenery.json",
                entities=[
                    _scenery(2213, "Bank booth", attributes={"placement_count": 16}),
                    _scenery(2214, "Bank booth", attributes={"placement_count": 6}),
                    _scenery(2215, "Bank booth", attributes={"placement_count": 28}),
                ],
            )
        ]
    )
    standing = next(one for one in snapshot.entities if not one.is_variant)
    assert isinstance(standing.attributes, SceneryAttributes)
    assert standing.attributes.placement_count == 50


def test_two_sorts_of_thing_sharing_a_name_are_never_folded_together() -> None:
    """`Monkey Madness` is a quest and a piece of music, and which was meant is a
    question for whoever asked, not something to settle by folding.
    """
    snapshot = merge(
        [
            _source(
                "mixed.json",
                entities=[
                    {"type": "quest", "id": 75, "name": "Monkey Madness"},
                    {"type": "music", "id": 303, "name": "Monkey Madness"},
                ],
            )
        ]
    )
    assert not [entity for entity in snapshot.entities if entity.is_variant]


def test_a_name_only_one_record_answers_to_is_left_exactly_as_it_was() -> None:
    snapshot = merge([_source("items.json", entities=[_item(4587, "Dragon scimitar")])])
    assert snapshot.entities[0].canonical_id is None
    assert snapshot.entities[0].searchable is True


def test_a_record_the_build_never_publishes_is_not_folded_onto_a_name() -> None:
    """A hidden record is not an answer, so folding it would only make the name it
    was given look busier than it is.
    """
    snapshot = merge(
        [
            _source(
                "npcs.json",
                entities=[
                    _npc(1, "Tormented demon"),
                    _npc(2, "Tormented demon", visibility="hidden"),
                ],
            )
        ]
    )
    assert not [entity for entity in snapshot.entities if entity.is_variant]


def test_a_copy_the_sources_already_declared_is_never_folded_again() -> None:
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
    copied = next(one for one in snapshot.entities if one.is_variant)
    assert copied.variant_kind is VariantKind.NOTED


def test_every_count_the_registry_calls_totalled_is_one_the_fold_adds_up() -> None:
    assert frozenset({"placement_count"}) == _TOTALLED


def _drop(src: str, dst: str) -> dict[str, Any]:
    return {
        "src": src,
        "rel": "drops",
        "dst": dst,
        "attributes": {"weight": 1.0, "denominator": 128.0},
    }


def test_a_link_arriving_at_a_folded_copy_arrives_at_the_name_instead() -> None:
    """`dropped_by` used to answer with the same creature twice over, told apart only
    by numbers no answer is allowed to print.
    """
    snapshot = merge(
        [
            _source(
                "drops.json",
                entities=[
                    _npc(1592, "Steel dragon"),
                    _npc(3590, "Steel dragon"),
                    _item(536, "Dragon bones"),
                ],
                edges=[
                    _drop("npc:1592", "item:536"),
                    _drop("npc:3590", "item:536"),
                ],
            )
        ]
    )
    assert [str(edge.src) for edge in snapshot.edges] == ["npc:1592"]


def test_a_link_between_two_records_one_name_folds_is_dropped_not_looped() -> None:
    """Two places called `Varrock` cannot sensibly be part of each other once one
    name stands for both.
    """
    snapshot = merge(
        [
            _source(
                "places.json",
                entities=[
                    {"type": "location", "id": 1, "name": "Varrock"},
                    {"type": "location", "id": 2, "name": "Varrock"},
                ],
                edges=[{"src": "location:2", "rel": "part_of", "dst": "location:1"}],
            )
        ]
    )
    assert snapshot.edges == ()


def test_a_link_the_fold_never_touched_keeps_the_ends_it_was_written_with() -> None:
    snapshot = merge(
        [
            _source(
                "drops.json",
                entities=[_npc(50, KBD), _item(536, "Dragon bones")],
                edges=[_drop("npc:50", "item:536")],
            )
        ]
    )
    edge = snapshot.edges[0]
    assert (str(edge.src), str(edge.dst)) == ("npc:50", "item:536")


def test_a_link_written_to_a_copy_the_sources_declared_moves_too() -> None:
    """A written-up ore is the same ore to whoever asked, and the record it copies is
    the one carrying a price. A shop stocking eight of these used to answer with eight
    names and not a price among them.
    """
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
                    _npc(50, KBD),
                ],
                edges=[_drop("npc:50", "item:4588")],
            )
        ]
    )
    assert str(snapshot.edges[0].dst) == "item:4587"


def test_where_a_link_and_a_moved_one_collide_the_written_one_survives() -> None:
    """Thirty-five creatures drop both an ore and the written-up form of it, and the
    rate that should stand is the one recorded against the ore itself.
    """
    from wiki_api.domain.relationships import DropEdgeAttributes

    written = _drop("npc:50", "item:4587")
    written["attributes"] = {"weight": 25.0, "denominator": 128.0}
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
                    _npc(50, KBD),
                ],
                edges=[_drop("npc:50", "item:4588"), written],
            )
        ]
    )
    assert len(snapshot.edges) == 1
    kept = snapshot.edges[0].attributes
    assert isinstance(kept, DropEdgeAttributes)
    assert kept.weight == 25.0


def test_a_link_a_thing_had_with_itself_all_along_is_kept() -> None:
    """A hundred and fifteen weapons are their own ammunition, and a fold that reads
    every loop as one it made would throw all of them away.
    """
    snapshot = merge(
        [
            _source(
                "items.json",
                entities=[_item(732, "Holy water")],
                edges=[
                    {
                        "src": "item:732",
                        "rel": "uses_ammunition",
                        "dst": "item:732",
                    }
                ],
            )
        ]
    )
    assert [str(edge.dst) for edge in snapshot.edges] == ["item:732"]
