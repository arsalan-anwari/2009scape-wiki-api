"""Read the game's music track list into the pieces of music a player can unlock."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.space import SpawnKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.places import folded
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import MUSIC_TRACKS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.music import Track
    from wiki_api.pipeline.places import Gazetteer
    from wiki_api.pipeline.sources.staged import StagedSources

MUSIC_SOURCE: Final = "music_location_unlocks.txt"
PARTITION_SOURCE: Final = "music_regions.json"
SCOPED = re.compile(
    r"^(?:during|after)\s+(?:the\s+)?"
    r"(?P<named>.*?)"
    r"(?:\s+(?:quest|minigame|random event))?$",
    re.IGNORECASE,
)
LEADING_THE = re.compile(r"^the")
TRACKS_READ: Final = (
    "{count} tracks the dump describes, {dropped} placeholder rows left"
)
REGIONS_READ: Final = (
    "{count} map squares the partition keys to a track, giving {landed} places a "
    "track because they stand inside one"
)
UNMATCHED: Final = (
    "{count} tracks unlock during something this build holds no entity for, such as "
    "{sample}"
)
SAMPLE_WIDTH: Final = 3


def read_music(staged: StagedSources) -> SourceOutcome:
    """Write an entity for every track the dump really describes."""
    if not staged.has_staged(MUSIC_TRACKS.staged):
        return SourceOutcome(source=MUSIC_SOURCE, read=_document(staged, (), ()))
    tracks = staged.tracks(MUSIC_TRACKS)
    kept = published(tracks)
    counted = _region_counts(staged)
    entities = [_entity(track, counted.get(track.file_id, 0)) for track in kept]
    return SourceOutcome(
        source=MUSIC_SOURCE,
        read=_document(staged, entities, ()),
        notes=(TRACKS_READ.format(count=len(kept), dropped=len(tracks) - len(kept)),),
    )


def read_music_regions(
    staged: StagedSources, known: frozenset[EntityKey], places: Gazetteer
) -> SourceOutcome:
    """Say which named places each track is heard in, one edge per pair."""
    if not staged.has_staged(MUSIC_TRACKS.staged):
        return SourceOutcome(source=PARTITION_SOURCE, read=_document(staged, (), ()))
    regions = staged.music_regions(MUSIC_TRACKS)
    landed: dict[tuple[int, EntityKey], int] = {}
    for region in regions:
        track = EntityKey(type=EntityType.MUSIC, id=region.track)
        if track not in known:
            continue
        for place in places.within(region.area):
            landed[(region.track, place)] = landed.get((region.track, place), 0) + 1
    edges = [
        _region_edge(track, place, squares)
        for (track, place), squares in sorted(
            landed.items(), key=lambda pair: (pair[0][0], pair[0][1].id)
        )
    ]
    return SourceOutcome(
        source=PARTITION_SOURCE,
        read=_document(staged, (), edges, source_file=PARTITION_SOURCE),
        notes=(REGIONS_READ.format(count=len(regions), landed=len(edges)),),
    )


def read_quest_music(
    staged: StagedSources, known: frozenset[EntityKey], quests: Mapping[str, EntityKey]
) -> SourceOutcome:
    """Join a track to the quest its unlock sentence names."""
    if not staged.has_staged(MUSIC_TRACKS.staged):
        return SourceOutcome(source=MUSIC_SOURCE, read=_document(staged, (), ()))
    by_name = {_folded_title(name): key for name, key in quests.items()}
    edges = []
    missed: list[str] = []
    for track in published(staged.tracks(MUSIC_TRACKS)):
        named = scoped_to(track)
        if not named:
            continue
        key = EntityKey(type=EntityType.MUSIC, id=track.file_id)
        quest = by_name.get(_folded_title(named))
        if quest is None:
            missed.append(named)
            continue
        if key in known:
            edges.append(_quest_edge(key, quest))
    return SourceOutcome(
        source=MUSIC_SOURCE,
        read=_document(staged, (), edges),
        notes=_unmatched_note(missed),
    )


def published(tracks: Sequence[Track]) -> tuple[Track, ...]:
    """The rows that describe a track rather than standing in for one."""
    return tuple(track for track in tracks if not track.is_placeholder)


def scoped_to(track: Track) -> str:
    """What the unlock sentence says this track plays during, or nothing."""
    found = SCOPED.match(track.note)
    return found["named"].strip() if found else ""


def _folded_title(named: str) -> str:
    return LEADING_THE.sub("", folded(named))


def _region_counts(staged: StagedSources) -> dict[int, int]:
    counted: dict[int, int] = {}
    for region in staged.music_regions(MUSIC_TRACKS):
        counted[region.track] = counted.get(region.track, 0) + 1
    return counted


def _entity(track: Track, squares: int) -> Mapping[str, Any]:
    told: dict[str, Any] = {"region_count": squares}
    if track.set_name:
        told["trackset"] = track.set_name
    if track.note:
        told["unlock_note"] = track.note
    return {
        "type": EntityType.MUSIC.value,
        "id": track.file_id,
        "name": track.name,
        "source_ref": f"{MUSIC_SOURCE}#{track.array_id}",
        "attributes": told,
    }


def _region_edge(track: int, place: EntityKey, squares: int) -> Mapping[str, Any]:
    return {
        "src": {"type": EntityType.MUSIC.value, "id": track},
        "rel": RelationshipType.LOCATED_IN.value,
        "dst": {"type": place.type.value, "id": place.id},
        "attributes": {"spawn_kind": SpawnKind.MUSIC_REGION.value, "amount": squares},
    }


def _quest_edge(track: EntityKey, quest: EntityKey) -> Mapping[str, Any]:
    return {
        "src": {"type": track.type.value, "id": track.id},
        "rel": RelationshipType.HEARD_DURING.value,
        "dst": {"type": quest.type.value, "id": quest.id},
        "attributes": {},
    }


def _unmatched_note(missed: Sequence[str]) -> tuple[str, ...]:
    if not missed:
        return ()
    named = sorted(set(missed))
    return (
        UNMATCHED.format(count=len(missed), sample=", ".join(named[:SAMPLE_WIDTH])),
    )


def _document(
    staged: StagedSources,
    entities: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    source_file: str = MUSIC_SOURCE,
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": MUSIC_TRACKS.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CONFIG.value,
                "source_file": source_file,
                "game_version": str(staged.version_of(MUSIC_TRACKS.staged)),
                "entities": list(entities),
                "edges": list(edges),
            },
        }
    )


# test cases


DUMP = {
    "tracks": [
        {
            "file_id": 177,
            "array_id": 0,
            "name": "Adventure",
            "trackset": "Varrock",
            "unlock": "at Varrock Palace.",
        },
        {
            "file_id": 102,
            "array_id": 2,
            "name": "Alone",
            "trackset": '"Only defined"',
            "unlock": "during the Golem.",
        },
        {
            "file_id": 588,
            "array_id": 3,
            "name": "Pest Control",
            "trackset": '"Only defined"',
            "unlock": "during the Pest Control minigame.",
        },
        {
            "file_id": 177,
            "array_id": 4,
            "name": "",
            "trackset": '"Only defined"',
            "unlock": "not unlockable!",
        },
    ]
}
PARTITION = [
    {"region": "12850", "id": "177"},
    {"region": "12851", "id": "177"},
    {"region": "11317", "id": "102"},
]


def _staged(tmp_path: Any) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {
            MUSIC_TRACKS.staged: json.dumps(DUMP),
            MUSIC_TRACKS.config.staged: json.dumps(PARTITION),
        },
    )


def _gazetteer() -> Gazetteer:
    from wiki_api.domain.space import Area, Coordinate
    from wiki_api.pipeline.places import Gazetteer as Found
    from wiki_api.pipeline.places import Place

    return Found(
        [
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=1),
                centre=Area.of_region(12850).centre,
            ),
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=2),
                centre=Area.of_region(12851).centre,
            ),
            Place(
                key=EntityKey(type=EntityType.LOCATION, id=3),
                centre=Coordinate(x=3210, y=3220),
            ),
        ]
    )


def _known() -> frozenset[EntityKey]:
    return frozenset(
        {
            EntityKey(type=EntityType.MUSIC, id=177),
            EntityKey(type=EntityType.MUSIC, id=102),
            EntityKey(type=EntityType.MUSIC, id=588),
        }
    )


def test_a_track_becomes_a_piece_of_music_numbered_by_its_own_file(
    tmp_path: Any,
) -> None:
    entities = read_music(_staged(tmp_path)).read.document.entities
    named = [entity.name for entity in entities]
    assert named == ["Adventure", "Alone", "Pest Control"]
    assert entities[0].id == 177
    assert entities[0].attributes["trackset"] == "Varrock"
    assert entities[0].attributes["unlock_note"] == "at Varrock Palace"


def test_a_placeholder_row_never_becomes_a_piece_of_music(tmp_path: Any) -> None:
    outcome = read_music(_staged(tmp_path))
    assert len(outcome.read.document.entities) == 3
    assert "1 placeholder rows left" in outcome.notes[0]


def test_the_placeholder_set_is_not_published_as_a_set(tmp_path: Any) -> None:
    entities = read_music(_staged(tmp_path)).read.document.entities
    assert "trackset" not in entities[1].attributes


def test_a_track_says_how_much_of_the_world_plays_it(tmp_path: Any) -> None:
    entities = read_music(_staged(tmp_path)).read.document.entities
    assert entities[0].attributes["region_count"] == 2
    assert entities[2].attributes["region_count"] == 0


def test_a_map_square_lands_the_track_in_the_place_that_holds_it(
    tmp_path: Any,
) -> None:
    outcome = read_music_regions(_staged(tmp_path), _known(), _gazetteer())
    edges = outcome.read.document.edges
    assert len(edges) == 3
    assert {edge.dst.id for edge in edges} == {1, 2, 3}
    assert edges[0].attributes["spawn_kind"] == SpawnKind.MUSIC_REGION.value


def test_every_place_standing_in_a_square_takes_its_track_not_just_the_nearest(
    tmp_path: Any,
) -> None:
    """Two places inside one square both hear it, and a place outside hears nothing.

    Asking which place is nearest would answer with one of them and would answer for
    squares holding no place at all, which is a guess rather than a reading.
    """
    edges = read_music_regions(
        _staged(tmp_path), _known(), _gazetteer()
    ).read.document.edges
    heard = {(edge.src.id, edge.dst.id) for edge in edges}
    assert (177, 1) in heard
    assert (177, 3) in heard
    assert not [edge for edge in edges if edge.src.id == 102]


def test_a_square_no_place_holds_lands_nothing(tmp_path: Any) -> None:
    from wiki_api.pipeline.places import Gazetteer as Found

    outcome = read_music_regions(_staged(tmp_path), _known(), Found([]))
    assert outcome.read.document.edges == ()
    assert "giving 0 places a track" in outcome.notes[0]


def test_a_track_nobody_published_is_heard_nowhere(tmp_path: Any) -> None:
    outcome = read_music_regions(_staged(tmp_path), frozenset(), _gazetteer())
    assert outcome.read.document.edges == ()


def test_the_unlock_sentence_joins_a_track_to_the_quest_it_names(
    tmp_path: Any,
) -> None:
    quests = {"The Golem": EntityKey(type=EntityType.QUEST, id=7)}
    outcome = read_quest_music(_staged(tmp_path), _known(), quests)
    edges = outcome.read.document.edges
    assert len(edges) == 1
    assert edges[0].src.id == 102
    assert edges[0].dst.id == 7


def test_something_this_build_holds_no_entity_for_is_counted_rather_than_joined(
    tmp_path: Any,
) -> None:
    outcome = read_quest_music(_staged(tmp_path), _known(), {})
    assert outcome.read.document.edges == ()
    assert "Golem" in outcome.notes[0]
    assert "Pest Control" in outcome.notes[0]


def test_a_sentence_about_a_place_names_no_quest() -> None:
    from wiki_api.pipeline.music import Track

    at_a_place = Track(
        file_id=1,
        array_id=0,
        name="Adventure",
        trackset="Varrock",
        unlock="at Varrock.",
    )
    during = Track(
        file_id=2, array_id=1, name="Alone", trackset="", unlock="during the Golem."
    )
    assert scoped_to(at_a_place) == ""
    assert scoped_to(during) == "Golem"


def test_the_words_naming_the_sort_of_content_are_not_part_of_its_name() -> None:
    from wiki_api.pipeline.music import Track

    minigame = Track(
        file_id=1,
        array_id=0,
        name="Trawler",
        trackset="Port",
        unlock="during the Fishing Trawler minigame.",
    )
    assert scoped_to(minigame) == "Fishing Trawler"


def test_with_nothing_staged_no_music_is_invented(tmp_path: Any) -> None:
    from tests.sources import staged_from

    staged = staged_from(tmp_path, {})
    assert read_music(staged).read.document.entities == ()
    heard = read_music_regions(staged, frozenset(), _gazetteer())
    assert heard.read.document.edges == ()
    assert read_quest_music(staged, frozenset(), {}).read.document.edges == ()
