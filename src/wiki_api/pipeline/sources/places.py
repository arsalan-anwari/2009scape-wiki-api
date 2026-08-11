"""Turn the three sources that talk about the map into one list of named places."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityType
from wiki_api.domain.space import Area, LocationKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.cache.maplabels import MapLabel
from wiki_api.pipeline.places import folded
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import (
    MAP_LABEL_EXTRACT,
    MUSIC_TRACKS,
    TELEPORT_ANCHORS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.places import PlacedRegion
    from wiki_api.pipeline.sources.staged import StagedSources

LABEL_SOURCE: Final = "maplabels"
PARTITION_SOURCE: Final = "music_regions.json"
DRAWN: Final = (
    "{count} places the game's own map draws a name over, {bounded} of them given "
    "tiles by the music partition"
)
CORROBORATED: Final = (
    "{count} places the map draws no label for, where the music partition and the "
    "teleport list agree on the name and the point falls inside the tiles"
)
UNSETTLED: Final = (
    "{count} regions the partition points at a place for that no source names, left "
    "unpublished rather than published without a name"
)


@dataclass(frozen=True)
class NamedPlace:
    """One place a source names, and whatever tiles another source lends it."""

    key: str
    name: str
    x: int
    y: int
    rank: int
    regions: tuple[PlacedRegion, ...]

    @property
    def home(self) -> PlacedRegion | None:
        """The region carrying this name that the point actually lands in."""
        return next((region for region in self.regions if self._holds(region)), None)

    @property
    def bounds(self) -> Area | None:
        """Every region the partition gave this name when those form one solid
        rectangle, the home region when they do not, and nothing when none holds it.
        """
        home = self.home
        if home is None:
            return None
        joined = home.area
        for region in self.regions:
            joined = joined.joined(region.area)
        return joined if self._is_solid(joined, home) else home.area

    @property
    def region_id(self) -> int:
        home = self.home
        return home.region if home is not None else _region_of(self.x, self.y)

    def _holds(self, region: PlacedRegion) -> bool:
        return (
            region.min_x <= self.x <= region.max_x
            and region.min_y <= self.y <= region.max_y
        )

    def _is_solid(self, joined: Area, home: PlacedRegion) -> bool:
        across = (joined.max_x - joined.min_x + 1) // (home.max_x - home.min_x + 1)
        up = (joined.max_y - joined.min_y + 1) // (home.max_y - home.min_y + 1)
        return across * up == len(self.regions)


def place_keys(staged: StagedSources) -> tuple[str, ...]:
    """Every natural key the sources land, in a stable order."""
    drawn = drawn_places(staged)
    agreed = corroborated_places(staged, {place.key for place in drawn})
    return tuple(sorted(place.key for place in (*drawn, *agreed)))


def drawn_places(staged: StagedSources) -> tuple[NamedPlace, ...]:
    """Every place the world map writes a name over."""
    if not staged.has_extract(MAP_LABEL_EXTRACT):
        return ()
    named = _named_regions(staged)
    found = [
        NamedPlace(
            key=folded(label.name),
            name=label.name,
            x=label.x,
            y=label.y,
            rank=label.rank,
            regions=tuple(named.get(folded(label.name), ())),
        )
        for label in _labels(staged)
    ]
    return _first_of_each(found)


def corroborated_places(
    staged: StagedSources, taken: set[str]
) -> tuple[NamedPlace, ...]:
    """Every place the map draws no label for that the other two sources agree on."""
    if not staged.has_staged(MUSIC_TRACKS.staged) or not staged.has_staged(
        TELEPORT_ANCHORS.staged
    ):
        return ()
    sheet = staged.anchors(TELEPORT_ANCHORS)
    found = []
    for key, regions in sorted(_named_regions(staged).items()):
        if key in taken:
            continue
        anchor = sheet.named(regions[0].place)
        if anchor is None:
            continue
        place = NamedPlace(
            key=key,
            name=regions[0].place,
            x=anchor.x,
            y=anchor.y,
            rank=0,
            regions=tuple(regions),
        )
        if place.home is not None:
            found.append(place)
    return tuple(found)


def read_map_places(
    staged: StagedSources, allocation: IdentityAllocation
) -> SourceOutcome:
    """Write a location for every name the world map draws."""
    places = drawn_places(staged)
    bounded = sum(1 for place in places if place.bounds is not None)
    return SourceOutcome(
        source=LABEL_SOURCE,
        read=_document(
            staged,
            MAP_LABEL_EXTRACT.staged,
            SourceKind.GAME_CACHE,
            LABEL_SOURCE,
            [_entity(place, allocation, LABEL_SOURCE) for place in places],
        ),
        notes=(DRAWN.format(count=len(places), bounded=bounded),),
    )


def read_agreed_places(
    staged: StagedSources, allocation: IdentityAllocation
) -> SourceOutcome:
    """Write a location for every place the map misses and the other two agree on."""
    drawn = {place.key for place in drawn_places(staged)}
    places = corroborated_places(staged, drawn)
    settled = drawn | {place.key for place in places}
    unsettled = sum(1 for key in _named_regions(staged) if key not in settled)
    return SourceOutcome(
        source=PARTITION_SOURCE,
        read=_document(
            staged,
            MUSIC_TRACKS.staged,
            SourceKind.GAME_CONFIG,
            PARTITION_SOURCE,
            [_entity(place, allocation, MUSIC_TRACKS.staged) for place in places],
        ),
        notes=(
            CORROBORATED.format(count=len(places)),
            UNSETTLED.format(count=unsettled),
        ),
    )


def _labels(staged: StagedSources) -> tuple[MapLabel, ...]:
    return tuple(
        MapLabel.model_validate(record) for record in staged.extract(MAP_LABEL_EXTRACT)
    )


def _named_regions(staged: StagedSources) -> dict[str, list[PlacedRegion]]:
    if not staged.has_staged(MUSIC_TRACKS.staged):
        return {}
    named: dict[str, list[PlacedRegion]] = {}
    for region in staged.placed_regions(MUSIC_TRACKS):
        if region.place:
            named.setdefault(folded(region.place), []).append(region)
    return named


def _first_of_each(places: Sequence[NamedPlace]) -> tuple[NamedPlace, ...]:
    """One place per name, keeping the first the map draws, sorted by key."""
    kept: dict[str, NamedPlace] = {}
    for place in places:
        kept.setdefault(place.key, place)
    return tuple(kept[key] for key in sorted(kept))


def _region_of(x: int, y: int) -> int:
    from wiki_api.domain.space import Coordinate

    return Coordinate(x=x, y=y).region_id


def _entity(
    place: NamedPlace, allocation: IdentityAllocation, told_by: str
) -> Mapping[str, Any]:
    place_id = allocation.id_of(place.key)
    if place_id is None:
        raise UnallocatedIdentity(EntityType.LOCATION.value, place.key)
    return {
        "type": EntityType.LOCATION.value,
        "id": place_id,
        "name": place.name,
        "source_key": place.key,
        "source_ref": f"{told_by}#{place.region_id}",
        "attributes": _attributes(place),
    }


def _attributes(place: NamedPlace) -> Mapping[str, Any]:
    told: dict[str, Any] = {
        "kind": LocationKind.AREA.value,
        "centre": {"x": place.x, "y": place.y, "plane": 0},
        "region_id": place.region_id,
    }
    bounds = place.bounds
    if bounds is not None:
        told["bounds"] = {
            "min_x": bounds.min_x,
            "min_y": bounds.min_y,
            "max_x": bounds.max_x,
            "max_y": bounds.max_y,
            "plane": 0,
        }
    return told


def _document(
    staged: StagedSources,
    origin: str,
    kind: SourceKind,
    source_file: str,
    entities: Sequence[Mapping[str, Any]],
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": origin,
            "document": {
                "schema": 1,
                "source": kind.value,
                "source_file": source_file,
                "game_version": str(staged.version_of(origin)),
                "entities": list(entities),
            },
        }
    )


# test cases


def _staged(tmp_path: Any, labels: Sequence[Mapping[str, Any]] = ()) -> StagedSources:
    import json

    from tests.sources import staged_from

    tracks = {
        "tracks": [
            {
                "file_id": 1,
                "array_id": 0,
                "name": "Adventure",
                "trackset": "Misthalin",
                "unlock": "at Lumbridge.",
            },
            {
                "file_id": 2,
                "array_id": 1,
                "name": "Autumn Voyage",
                "trackset": "Kandarin",
                "unlock": "at Catherby.",
            },
        ]
    }
    return staged_from(
        tmp_path,
        {
            MAP_LABEL_EXTRACT.staged: json.dumps(list(labels)),
            MUSIC_TRACKS.staged: json.dumps(tracks),
            MUSIC_TRACKS.config.staged: json.dumps(
                [
                    {"region": "12850", "id": "1"},
                    {"region": "12851", "id": "1"},
                    {"region": "11317", "id": "2"},
                ]
            ),
            TELEPORT_ANCHORS.staged: json.dumps(
                {
                    "anchors": [
                        {"name": "Catherby", "folded": "catherby", "x": 2821, "y": 3432}
                    ],
                    "lines": 1,
                    "unread": 0,
                }
            ),
        },
    )


def _allocation(*keys: str) -> IdentityAllocation:
    from wiki_api.pipeline.identity import IdentityAllocation

    return IdentityAllocation(
        type=EntityType.LOCATION,
        ids={key: number for number, key in enumerate(keys, 1)},
    )


def _drawn(name: str, rank: int, x: int, y: int) -> dict[str, Any]:
    return {"name": name, "rank": rank, "x": x, "y": y}


def test_a_label_becomes_a_place_that_takes_the_tiles_the_partition_gives(
    tmp_path: Any,
) -> None:
    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    outcome = read_map_places(staged, _allocation("lumbridge"))
    entity = outcome.read.document.entities[0]
    assert entity.name == "Lumbridge"
    assert entity.attributes["bounds"]["max_y"] == 3327
    assert "1 of them given tiles" in outcome.notes[0]


def test_a_label_the_partition_says_nothing_about_still_lands(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [_drawn("Baxtorian Falls", 8, 2515, 3462)])
    entity = read_map_places(
        staged, _allocation("baxtorianfalls")
    ).read.document.entities[0]
    assert "bounds" not in entity.attributes
    assert entity.attributes["centre"] == {"x": 2515, "y": 3462, "plane": 0}


def test_a_place_the_map_never_draws_still_lands_on_the_older_rule(
    tmp_path: Any,
) -> None:
    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    outcome = read_agreed_places(staged, _allocation("catherby"))
    assert [entity.name for entity in outcome.read.document.entities] == ["Catherby"]


def test_a_name_the_map_draws_is_not_landed_twice(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [_drawn("Catherby", 8, 2821, 3432)])
    assert read_agreed_places(staged, _allocation()).read.document.entities == ()


def test_every_key_the_sources_land_is_offered_for_numbering(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    assert place_keys(staged) == ("catherby", "lumbridge")


def test_a_place_nobody_numbered_stops_the_build(tmp_path: Any) -> None:
    import pytest

    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    with pytest.raises(UnallocatedIdentity):
        read_map_places(staged, _allocation())


def test_with_nothing_staged_neither_reader_invents_a_place(tmp_path: Any) -> None:
    from tests.sources import staged_from

    staged = staged_from(tmp_path, {})
    assert read_map_places(staged, _allocation()).read.document.entities == ()
    assert read_agreed_places(staged, _allocation()).read.document.entities == ()
    assert place_keys(staged) == ()


def _regions() -> tuple[PlacedRegion, ...]:
    from wiki_api.pipeline.places import PlacedRegion

    def square(region: int, place: str) -> PlacedRegion:
        area = Area.of_region(region)
        return PlacedRegion(
            region=region,
            min_x=area.min_x,
            min_y=area.min_y,
            max_x=area.max_x,
            max_y=area.max_y,
            track=1,
            place=place,
        )

    return (
        square(12850, "Lumbridge"),
        square(12851, "Lumbridge"),
        square(12853, "Varrock"),
        square(9033, "Nowhere Anybody Went"),
    )


def _grouped() -> dict[str, list[PlacedRegion]]:
    named: dict[str, list[PlacedRegion]] = {}
    for region in _regions():
        named.setdefault(folded(region.place), []).append(region)
    return named


def _place(name: str, x: int, y: int, rank: int = 8) -> NamedPlace:
    return NamedPlace(
        key=folded(name),
        name=name,
        x=x,
        y=y,
        rank=rank,
        regions=tuple(_grouped().get(folded(name), ())),
    )


def test_a_place_the_partition_agrees_with_takes_the_tiles_it_gives() -> None:
    bounds = _place("Lumbridge", 3222, 3218).bounds
    assert bounds is not None
    assert (bounds.min_x, bounds.min_y) == (3200, 3200)
    assert (bounds.max_x, bounds.max_y) == (3263, 3327)


def test_a_place_of_one_region_covers_that_region() -> None:
    bounds = _place("Varrock", 3210, 3424).bounds
    assert bounds == Area.of_region(12853)


def test_a_label_the_partition_never_names_keeps_its_point_and_no_tiles() -> None:
    place = _place("Baxtorian Falls", 2515, 3462)
    assert place.bounds is None
    assert place.region_id == 2515 // 64 * 256 + 3462 // 64


def test_a_label_whose_point_misses_its_own_named_tiles_gets_no_extent() -> None:
    place = _place("Lumbridge", 100, 100)
    assert place.bounds is None
    assert place.home is None


def test_scattered_regions_do_not_claim_the_rectangle_between_them() -> None:
    from wiki_api.pipeline.places import PlacedRegion

    def square(region: int) -> PlacedRegion:
        area = Area.of_region(region)
        return PlacedRegion(
            region=region,
            min_x=area.min_x,
            min_y=area.min_y,
            max_x=area.max_x,
            max_y=area.max_y,
            track=1,
            place="Port",
        )

    place = NamedPlace(
        key="port",
        name="Port",
        x=3222,
        y=3218,
        rank=8,
        regions=(square(12850), square(13500)),
    )
    assert place.bounds == Area.of_region(12850)


def test_the_same_name_drawn_twice_lands_once() -> None:
    twice = (_place("Bandit Camp", 3036, 3689), _place("Bandit Camp", 3175, 2977))
    kept = _first_of_each(twice)
    assert len(kept) == 1
    assert (kept[0].x, kept[0].y) == (3036, 3689)


def test_the_attributes_carry_the_point_and_leave_out_an_extent_nobody_gave() -> None:
    told = _attributes(_place("Baxtorian Falls", 2515, 3462))
    assert told["centre"] == {"x": 2515, "y": 3462, "plane": 0}
    assert "bounds" not in told


def test_the_attributes_carry_an_extent_when_the_partition_gave_one() -> None:
    told = _attributes(_place("Varrock", 3210, 3424))
    assert told["bounds"]["min_x"] == 3200
