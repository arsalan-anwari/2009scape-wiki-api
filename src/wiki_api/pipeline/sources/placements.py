"""Land the things standing in the world in the places that hold them.

The cache gives a tile per object; those fold onto one edge per (thing, place) pair
carrying how many stand there, rather than one edge per tile.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.space import Coordinate, SpawnKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import SkipReason
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import PLACEMENT_EXTRACT

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.places import Gazetteer
    from wiki_api.pipeline.sources.staged import StagedSources

OBJECT_ID_FIELD: Final = "object_id"
X_FIELD: Final = "x"
Y_FIELD: Final = "y"
PLANE_FIELD: Final = "plane"
SOURCE_FILE: Final = "placements"
STANDING_NOTE: Final = (
    "{pairs} pairs from {landed} of {read} placements, folded so a thing standing "
    "somewhere many times is one edge carrying how many"
)
NOWHERE_NOTE: Final = (
    "a tile becomes a placement only inside a place that holds it or near one that "
    "names itself, so the rest of the world waits on more places being named"
)


def read_standing(
    staged: StagedSources, known: frozenset[EntityKey], places: Gazetteer
) -> SourceOutcome:
    """Turn every placed object into one edge per place it stands in."""
    if not staged.has_extract(PLACEMENT_EXTRACT):
        return SourceOutcome(
            source=SOURCE_FILE, read=_document(staged, ()), notes=("nothing staged",)
        )
    counted: Counter[tuple[EntityKey, EntityKey]] = Counter()
    tallied: Counter[SkipReason] = Counter()
    read = 0
    landed = 0
    for record in staged.stream(PLACEMENT_EXTRACT):
        read += 1
        subject = EntityKey(type=EntityType.SCENERY, id=int(record[OBJECT_ID_FIELD]))
        if subject not in known:
            tallied[SkipReason.UNKNOWN_SUBJECT] += 1
            continue
        at = Coordinate(
            x=int(record[X_FIELD]),
            y=int(record[Y_FIELD]),
            plane=int(record[PLANE_FIELD]),
        )
        place = places.holding(at)
        if place is None:
            tallied[SkipReason.NO_PLACE] += 1
            continue
        landed += 1
        counted[(subject, place)] += 1
    edges = _edges(counted)
    return SourceOutcome(
        source=SOURCE_FILE,
        read=_document(staged, edges),
        tallied=dict(tallied),
        notes=(
            STANDING_NOTE.format(pairs=len(edges), landed=landed, read=read),
            NOWHERE_NOTE,
        ),
    )


def _edges(
    counted: Mapping[tuple[EntityKey, EntityKey], int],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "src": str(subject),
            "rel": RelationshipType.LOCATED_IN.value,
            "dst": str(place),
            "order_key": -standing,
            "source_ref": f"{SOURCE_FILE}#{subject.id}",
            "attributes": {
                "spawn_kind": SpawnKind.BUILT_IN.value,
                "amount": standing,
            },
        }
        for (subject, place), standing in sorted(
            counted.items(), key=lambda pair: (pair[0][0].id, pair[0][1].id)
        )
    )


def _revision(staged: StagedSources) -> str | None:
    if not staged.has_extract(PLACEMENT_EXTRACT):
        return None
    return staged.revision(PLACEMENT_EXTRACT.staged)


def _document(
    staged: StagedSources, edges: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": PLACEMENT_EXTRACT.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CACHE.value,
                "source_file": SOURCE_FILE,
                "game_version": str(staged.version_of(PLACEMENT_EXTRACT.staged)),
                "source_revision": _revision(staged),
                "edges": list(edges),
            },
        }
    )


# test cases


def _staged_with(tmp_path: Any, placements: Sequence[Mapping[str, Any]]) -> Any:
    import gzip
    import json

    from tests.sources import staged_from

    body = gzip.compress(
        b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in placements)
    )
    return staged_from(tmp_path, {PLACEMENT_EXTRACT.staged: body})


def _places() -> Gazetteer:
    from wiki_api.domain.space import Area
    from wiki_api.pipeline.places import Gazetteer, Place

    return Gazetteer(
        [
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=1),
                bounds=Area.of_region(12850),
            )
        ]
    )


def _known() -> frozenset[EntityKey]:
    return frozenset({EntityKey(type=EntityType.SCENERY, id=4306)})


def _placement(object_id: int, x: int, y: int, plane: int = 0) -> dict[str, Any]:
    return {"object_id": object_id, "x": x, "y": y, "plane": plane, "region": 12850}


def test_many_of_one_thing_in_one_place_fold_into_one_edge(tmp_path: Any) -> None:
    staged = _staged_with(
        tmp_path,
        [_placement(4306, 3210, 3210), _placement(4306, 3220, 3220)],
    )
    outcome = read_standing(staged, _known(), _places())
    edges = outcome.read.document.edges
    assert len(edges) == 1
    assert edges[0].attributes["amount"] == 2


def test_the_edge_says_the_thing_was_built_there_rather_than_spawned(
    tmp_path: Any,
) -> None:
    staged = _staged_with(tmp_path, [_placement(4306, 3210, 3210)])
    edge = read_standing(staged, _known(), _places()).read.document.edges[0]
    assert edge.attributes["spawn_kind"] == SpawnKind.BUILT_IN.value
    assert "at" not in edge.attributes


def test_the_commonest_thing_in_a_place_reads_first(tmp_path: Any) -> None:
    staged = _staged_with(
        tmp_path, [_placement(4306, 3210, 3210), _placement(4306, 3211, 3211)]
    )
    edge = read_standing(staged, _known(), _places()).read.document.edges[0]
    assert edge.order_key == -2


def test_a_tile_no_place_holds_is_counted_rather_than_dropped(tmp_path: Any) -> None:
    staged = _staged_with(tmp_path, [_placement(4306, 100, 100)])
    outcome = read_standing(staged, _known(), _places())
    assert outcome.read.document.edges == ()
    assert outcome.skipped_by_reason() == {"no_place": 1}


def test_a_thing_the_artifact_never_published_is_counted(tmp_path: Any) -> None:
    staged = _staged_with(tmp_path, [_placement(9999, 3210, 3210)])
    outcome = read_standing(staged, _known(), _places())
    assert outcome.read.document.edges == ()
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_the_report_says_how_much_of_the_world_landed(tmp_path: Any) -> None:
    staged = _staged_with(
        tmp_path, [_placement(4306, 3210, 3210), _placement(4306, 100, 100)]
    )
    told = read_standing(staged, _known(), _places()).notes[0]
    assert "1 pairs from 1 of 2 placements" in told


def test_nothing_staged_is_said_rather_than_raised(tmp_path: Any) -> None:
    from tests.sources import staged_from

    outcome = read_standing(staged_from(tmp_path, {}), _known(), _places())
    assert outcome.read.document.edges == ()
    assert outcome.notes == ("nothing staged",)
