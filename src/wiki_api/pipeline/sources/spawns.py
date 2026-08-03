"""Read the staged spawn files into placements inside the places overlays name."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.space import Area, Coordinate, SpawnKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, groups
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredConfig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

NPC_DECLARED: Final = DeclaredConfig(name="npc_spawns.json")
GROUND_DECLARED: Final = DeclaredConfig(name="ground_spawns.json")
NPC_ID_FIELD: Final = "npc_id"
ITEM_ID_FIELD: Final = "item_id"
LOCATIONS_FIELD: Final = "loc_data"
SPAWN_WIDTH: Final = 5
NO_PLACE_NOTE: Final = (
    "a coordinate only becomes a placement once an overlay names a place that "
    "contains it, so the world stays unnamed until the map is decoded"
)


@dataclass(frozen=True)
class Place:
    """One named place an overlay gave an extent to."""

    key: EntityKey
    bounds: Area

    @property
    def size(self) -> int:
        return (self.bounds.max_x - self.bounds.min_x + 1) * (
            self.bounds.max_y - self.bounds.min_y + 1
        )


class Places:
    """The places a coordinate can fall inside, smallest first."""

    def __init__(self, places: Sequence[Place] = ()) -> None:
        self._places = tuple(
            sorted(places, key=lambda place: (place.size, place.key.id))
        )

    def __len__(self) -> int:
        return len(self._places)

    def holding(self, point: Coordinate) -> EntityKey | None:
        """The smallest place whose extent covers this tile."""
        for place in self._places:
            if place.bounds.contains(point):
                return place.key
        return None


def read_npc_spawns(
    staged: StagedSources, known: frozenset[EntityKey], places: Places
) -> SourceOutcome:
    """Turn every npc spawn tile into a placement inside a named place."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in staged.records(NPC_DECLARED):
        npc_id = int(str(record[NPC_ID_FIELD]))
        npc = EntityKey(type=EntityType.NPC, id=npc_id)
        packed = groups(
            record.get(LOCATIONS_FIELD),
            NPC_DECLARED.name,
            str(npc_id),
            LOCATIONS_FIELD,
            SPAWN_WIDTH,
        )
        if npc not in known:
            skipped.extend(
                Skipped(
                    source=NPC_DECLARED.name,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(npc),
                )
                for _ in packed
            )
            continue
        for x, y, plane, _amount, _direction in packed:
            _place(
                npc,
                Coordinate(x=x, y=y, plane=plane),
                SpawnKind.NPC_SPAWN,
                {},
                places,
                NPC_DECLARED.name,
                edges,
                skipped,
            )
    return SourceOutcome(
        source=NPC_DECLARED.name,
        read=_document(staged, NPC_DECLARED, edges),
        skipped=tuple(skipped),
        notes=(NO_PLACE_NOTE,),
    )


def read_ground_spawns(
    staged: StagedSources, known: frozenset[EntityKey], places: Places
) -> SourceOutcome:
    """Turn every fixed item spawn into a placement inside a named place."""
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for record in staged.records(GROUND_DECLARED):
        item_id = int(str(record[ITEM_ID_FIELD]))
        item = EntityKey(type=EntityType.ITEM, id=item_id)
        packed = groups(
            record.get(LOCATIONS_FIELD),
            GROUND_DECLARED.name,
            str(item_id),
            LOCATIONS_FIELD,
            SPAWN_WIDTH,
        )
        if item not in known:
            skipped.extend(
                Skipped(
                    source=GROUND_DECLARED.name,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=str(item),
                )
                for _ in packed
            )
            continue
        for amount, x, y, plane, respawn in packed:
            _place(
                item,
                Coordinate(x=x, y=y, plane=plane),
                SpawnKind.GROUND_SPAWN,
                {"amount": max(amount, 1), "respawn_ticks": respawn},
                places,
                GROUND_DECLARED.name,
                edges,
                skipped,
            )
    return SourceOutcome(
        source=GROUND_DECLARED.name,
        read=_document(staged, GROUND_DECLARED, edges),
        skipped=tuple(skipped),
        notes=(NO_PLACE_NOTE,),
    )


def _place(
    subject: EntityKey,
    at: Coordinate,
    kind: SpawnKind,
    extra: Mapping[str, int],
    places: Places,
    source: str,
    edges: list[dict[str, Any]],
    skipped: list[Skipped],
) -> None:
    place = places.holding(at)
    if place is None:
        skipped.append(
            Skipped(source=source, reason=SkipReason.NO_PLACE, detail=str(at))
        )
        return
    edge = {
        "src": str(subject),
        "rel": RelationshipType.LOCATED_IN.value,
        "dst": str(place),
        "order_key": 0,
        "source_ref": f"{source}#{subject.id}",
        "attributes": {
            "at": {"x": at.x, "y": at.y, "plane": at.plane},
            "spawn_kind": kind.value,
            **extra,
        },
    }
    if edge not in edges:
        edges.append(edge)


def _document(
    staged: StagedSources,
    declared: DeclaredConfig,
    edges: Sequence[Mapping[str, Any]],
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": declared.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CONFIG.value,
                "source_file": declared.name,
                "game_version": str(staged.game_version(declared.staged)),
                "edges": list(edges),
            },
        }
    )


# test cases


def _sources(tmp_path: Any, npc: str, ground: str = "[]") -> StagedSources:
    from tests.sources import staged_from

    return staged_from(
        tmp_path, {NPC_DECLARED.staged: npc, GROUND_DECLARED.staged: ground}
    )


def _places() -> Places:
    return Places(
        [
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=1),
                bounds=Area(min_x=3200, min_y=3200, max_x=3300, max_y=3300),
            )
        ]
    )


def _known() -> frozenset[EntityKey]:
    return frozenset(
        {
            EntityKey(type=EntityType.NPC, id=1),
            EntityKey(type=EntityType.ITEM, id=20),
        }
    )


def test_a_spawn_inside_a_named_place_becomes_a_placement(tmp_path: Any) -> None:
    outcome = read_npc_spawns(
        _sources(tmp_path, '[{"npc_id": "1", "loc_data": "{3222,3221,0,1,3}-"}]'),
        _known(),
        _places(),
    )
    edge = outcome.read.document.edges[0]
    assert edge.dst.id == 1
    assert edge.attributes["at"] == {"x": 3222, "y": 3221, "plane": 0}
    assert edge.rel is RelationshipType.LOCATED_IN


def test_a_spawn_nobody_has_named_a_place_for_is_counted(tmp_path: Any) -> None:
    outcome = read_npc_spawns(
        _sources(tmp_path, '[{"npc_id": "1", "loc_data": "{100,100,0,1,3}-"}]'),
        _known(),
        _places(),
    )
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"no_place": 1}


def test_with_no_places_named_nothing_is_placed(tmp_path: Any) -> None:
    outcome = read_npc_spawns(
        _sources(tmp_path, '[{"npc_id": "1", "loc_data": "{3222,3221,0,1,3}-"}]'),
        _known(),
        Places(),
    )
    assert outcome.edges == 0
    assert outcome.skipped_by_reason() == {"no_place": 1}


def test_the_smallest_place_holding_a_tile_wins(tmp_path: Any) -> None:
    places = Places(
        [
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=1),
                bounds=Area(min_x=3000, min_y=3000, max_x=3500, max_y=3500),
            ),
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=2),
                bounds=Area(min_x=3220, min_y=3220, max_x=3230, max_y=3230),
            ),
        ]
    )
    outcome = read_npc_spawns(
        _sources(tmp_path, '[{"npc_id": "1", "loc_data": "{3222,3221,0,1,3}-"}]'),
        _known(),
        places,
    )
    assert outcome.read.document.edges[0].dst.id == 2


def test_one_tile_listed_twice_becomes_one_placement(tmp_path: Any) -> None:
    outcome = read_npc_spawns(
        _sources(
            tmp_path,
            '[{"npc_id": "1", "loc_data": "{3222,3221,0,1,3}-{3222,3221,0,1,3}-"}]',
        ),
        _known(),
        _places(),
    )
    assert outcome.edges == 1


def test_a_spawn_for_something_nothing_defines_is_counted(tmp_path: Any) -> None:
    outcome = read_npc_spawns(
        _sources(tmp_path, '[{"npc_id": "999", "loc_data": "{3222,3221,0,1,3}-"}]'),
        _known(),
        _places(),
    )
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_a_ground_spawn_reads_its_own_packing(tmp_path: Any) -> None:
    outcome = read_ground_spawns(
        _sources(
            tmp_path, "[]", '[{"item_id": "20", "loc_data": "{5,3250,3250,0,100}-"}]'
        ),
        _known(),
        _places(),
    )
    edge = outcome.read.document.edges[0]
    assert edge.attributes["at"] == {"x": 3250, "y": 3250, "plane": 0}
    assert edge.attributes["amount"] == 5
    assert edge.attributes["respawn_ticks"] == 100
    assert edge.attributes["spawn_kind"] == SpawnKind.GROUND_SPAWN.value


def test_a_ground_spawn_of_no_stated_amount_is_one(tmp_path: Any) -> None:
    outcome = read_ground_spawns(
        _sources(
            tmp_path, "[]", '[{"item_id": "20", "loc_data": "{0,3250,3250,0,50}-"}]'
        ),
        _known(),
        _places(),
    )
    assert outcome.read.document.edges[0].attributes["amount"] == 1
