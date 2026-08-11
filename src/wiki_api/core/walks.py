"""Follow a relationship either way over an entity and its variants, so one query
returns a total that can be trusted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from wiki_api.core.results import Block, Direction, Row, Walk
from wiki_api.core.values import edge_values, naming_of
from wiki_api.domain.page import Page
from wiki_api.domain.relationships import RELATIONSHIP_SPECS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.core.values import Naming
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityKey
    from wiki_api.domain.relationships import Edge, RelationshipType
    from wiki_api.repository.protocol import KnowledgeRepository

BLOCK_PAGE_SIZE: Final = 10


def key_set(repository: KnowledgeRepository, entity: Entity) -> tuple[EntityKey, ...]:
    """Collect every id a walk from this entity covers: the canonical one and its
    variants.
    """
    canonical = entity.canonical_key
    variants = repository.variants_of(canonical)
    return tuple(dict.fromkeys([canonical, *(variant.key for variant in variants)]))


def walk(
    repository: KnowledgeRepository,
    entity: Entity,
    rel: RelationshipType,
    direction: Direction,
    *,
    limit: int = BLOCK_PAGE_SIZE,
    offset: int = 0,
) -> Block:
    """One page of one relationship, with its neighbours already resolved."""
    return walk_keys(
        repository,
        entity.key,
        key_set(repository, entity),
        rel,
        direction,
        limit=limit,
        offset=offset,
    )


def walk_keys(
    repository: KnowledgeRepository,
    origin: EntityKey,
    keys: Sequence[EntityKey],
    rel: RelationshipType,
    direction: Direction,
    *,
    limit: int = BLOCK_PAGE_SIZE,
    offset: int = 0,
    naming: Naming | None = None,
) -> Block:
    """Walk over a key set the caller has already worked out."""
    if direction is Direction.FORWARD:
        edges = repository.edges_from(keys, rel=rel, limit=limit, offset=offset)
    else:
        edges = repository.edges_to(keys, rel=rel, limit=limit, offset=offset)
    neighbours = repository.get_entities(
        [far_key(edge, direction) for edge in edges.items]
    )
    return build_block(
        origin,
        rel,
        direction,
        edges,
        neighbours,
        naming=naming_of(repository) if naming is None else naming,
    )


def blocks_of(
    repository: KnowledgeRepository,
    entity: Entity,
    keys: Sequence[EntityKey],
    *,
    limit: int = BLOCK_PAGE_SIZE,
    naming: Naming | None = None,
) -> tuple[Block, ...]:
    """Build a block for every relationship of this type that has anything in it."""
    shared = naming_of(repository) if naming is None else naming
    blocks = []
    for spec in sorted(RELATIONSHIP_SPECS.values(), key=lambda spec: spec.order):
        for direction in Direction:
            reachable = (
                entity.type in spec.src_types
                if direction is Direction.FORWARD
                else entity.type in spec.dst_types
            )
            if not reachable:
                continue
            block = walk_keys(
                repository,
                entity.key,
                keys,
                spec.rel,
                direction,
                limit=limit,
                naming=shared,
            )
            if not block.is_empty:
                blocks.append(block)
    return tuple(blocks)


def far_key(edge: Edge, direction: Direction) -> EntityKey:
    """Pick the end of an edge a walk in this direction arrives at."""
    return edge.dst if direction is Direction.FORWARD else edge.src


def label_of(rel: RelationshipType, direction: Direction) -> str:
    """Read what this relationship is called this way round."""
    spec = RELATIONSHIP_SPECS[rel]
    if direction is Direction.FORWARD:
        return spec.forward_label
    return spec.inverse_label


def build_block(
    origin: EntityKey,
    rel: RelationshipType,
    direction: Direction,
    edges: Page[Edge],
    neighbours: Mapping[EntityKey, Entity],
    naming: Naming | None = None,
) -> Block:
    """Assemble one block out of edges and the entities they point at, counting rather
    than dropping the edges whose neighbour cannot be resolved.
    """
    rows = tuple(_rows(edges.items, direction, neighbours, naming))
    spec = RELATIONSHIP_SPECS[rel]
    return Block(
        walk=Walk(origin=origin, rel=rel, direction=direction),
        label=label_of(rel, direction),
        group=spec.group,
        order=spec.order,
        rows=Page[Row](
            items=rows,
            total=edges.total,
            limit=edges.limit,
            offset=edges.offset,
        ),
        suppressed=len(edges.items) - len(rows),
    )


def _rows(
    edges: Sequence[Edge],
    direction: Direction,
    neighbours: Mapping[EntityKey, Entity],
    naming: Naming | None = None,
) -> list[Row]:
    rows = []
    for edge in edges:
        neighbour = neighbours.get(far_key(edge, direction))
        if neighbour is None:
            continue
        rows.append(
            Row(
                link=neighbour.to_link(),
                type=neighbour.type,
                attributes=edge_values(edge, naming),
            )
        )
    return rows


# test cases


def _edge(**overrides: object) -> Edge:
    from wiki_api.domain.relationships import Edge

    payload: dict[str, object] = {
        "src": {"type": "npc", "id": 50},
        "rel": "drops",
        "dst": {"type": "item", "id": 536},
        "attributes": {"weight": 1.0, "denominator": 128.0},
        "provenance": {"source": "fixture", "game_version": "test"},
    }
    payload.update(overrides)
    return Edge.model_validate(payload)


def _entity(entity_type: str, entity_id: int, name: str) -> Entity:
    from wiki_api.domain.entity import Entity

    return Entity.model_validate(
        {
            "key": {"type": entity_type, "id": entity_id},
            "slug": name.lower().replace(" ", "-"),
            "name": name,
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )


def _page(*edges: Edge) -> Page[Edge]:
    from wiki_api.domain.relationships import Edge as EdgeModel

    return Page[EdgeModel](
        items=edges, total=len(edges), limit=BLOCK_PAGE_SIZE, offset=0
    )


def test_a_block_reads_forwards_and_backwards_with_the_right_words() -> None:
    from wiki_api.domain.relationships import RelationshipType

    assert label_of(RelationshipType.DROPS, Direction.FORWARD) == "Drops"
    assert label_of(RelationshipType.DROPS, Direction.REVERSE) == "Dropped by"


def test_a_walk_arrives_at_the_far_end_of_the_edge() -> None:
    edge = _edge()
    assert far_key(edge, Direction.FORWARD) == edge.dst
    assert far_key(edge, Direction.REVERSE) == edge.src


def test_a_row_carries_the_neighbour_and_what_the_link_records() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.domain.relationships import RelationshipType

    bones = _entity("item", 536, "Dragon bones")
    block = build_block(
        EntityKey(type=EntityType.NPC, id=50),
        RelationshipType.DROPS,
        Direction.FORWARD,
        _page(_edge()),
        {bones.key: bones},
    )
    row = block.rows.items[0]
    assert row.link.label == "Dragon bones"
    assert {value.key for value in row.attributes} >= {"weight", "denominator"}
    assert block.suppressed == 0


def test_an_edge_pointing_nowhere_is_counted_rather_than_shown() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.domain.relationships import RelationshipType

    block = build_block(
        EntityKey(type=EntityType.NPC, id=50),
        RelationshipType.DROPS,
        Direction.FORWARD,
        _page(_edge()),
        {},
    )
    assert block.rows.items == ()
    assert block.suppressed == 1
    assert block.rows.total == 1


def test_a_block_keeps_the_paging_the_repository_reported() -> None:
    from wiki_api.domain.identity import EntityKey, EntityType
    from wiki_api.domain.relationships import Edge as EdgeModel
    from wiki_api.domain.relationships import RelationshipType

    dragon = _entity("npc", 50, "King Black Dragon")
    edges = Page[EdgeModel](
        items=(_edge(dst={"type": "item", "id": 7980}),),
        total=1286,
        limit=1,
        offset=10,
    )
    block = build_block(
        EntityKey(type=EntityType.ITEM, id=7980),
        RelationshipType.DROPS,
        Direction.REVERSE,
        edges,
        {dragon.key: dragon},
    )
    assert block.rows.total == 1286
    assert block.rows.next_offset == 11
    assert block.rows.items[0].link.label == "King Black Dragon"
