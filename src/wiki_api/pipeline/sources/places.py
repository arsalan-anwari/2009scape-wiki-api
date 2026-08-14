"""Turn the names the world map draws into the places this project publishes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityType
from wiki_api.domain.space import Coordinate, LocationKind
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.cache.maplabels import MapLabel
from wiki_api.pipeline.places import folded
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import MAP_LABEL_EXTRACT

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.sources.staged import StagedSources

LABEL_SOURCE: Final = "maplabels"
DRAWN: Final = "{count} places the game's own map draws a name over"


@dataclass(frozen=True)
class NamedPlace:
    """One name the world map draws, and the tile it is drawn over."""

    key: str
    name: str
    x: int
    y: int
    rank: int

    @property
    def region_id(self) -> int:
        return Coordinate(x=self.x, y=self.y).region_id


def place_keys(staged: StagedSources) -> tuple[str, ...]:
    """Every natural key the map lands, in a stable order."""
    return tuple(sorted(place.key for place in drawn_places(staged)))


def drawn_places(staged: StagedSources) -> tuple[NamedPlace, ...]:
    """Every place the world map writes a name over."""
    if not staged.has_extract(MAP_LABEL_EXTRACT):
        return ()
    found = [
        NamedPlace(
            key=folded(label.name),
            name=label.name,
            x=label.x,
            y=label.y,
            rank=label.rank,
        )
        for label in _labels(staged)
    ]
    return _first_of_each(found)


def read_map_places(
    staged: StagedSources, allocation: IdentityAllocation
) -> SourceOutcome:
    """Write a location for every name the world map draws."""
    places = drawn_places(staged)
    return SourceOutcome(
        source=LABEL_SOURCE,
        read=_document(
            staged,
            MAP_LABEL_EXTRACT.staged,
            SourceKind.GAME_CACHE,
            LABEL_SOURCE,
            [_entity(place, allocation, LABEL_SOURCE) for place in places],
        ),
        notes=(DRAWN.format(count=len(places)),),
    )


def _labels(staged: StagedSources) -> tuple[MapLabel, ...]:
    return tuple(
        MapLabel.model_validate(record) for record in staged.extract(MAP_LABEL_EXTRACT)
    )


def _first_of_each(places: Sequence[NamedPlace]) -> tuple[NamedPlace, ...]:
    """One place per name, keeping the first the map draws, sorted by key."""
    kept: dict[str, NamedPlace] = {}
    for place in places:
        kept.setdefault(place.key, place)
    return tuple(kept[key] for key in sorted(kept))


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
    return {
        "kind": LocationKind.AREA.value,
        "centre": {"x": place.x, "y": place.y, "plane": 0},
        "region_id": place.region_id,
    }


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

    return staged_from(tmp_path, {MAP_LABEL_EXTRACT.staged: json.dumps(list(labels))})


def _allocation(*keys: str) -> IdentityAllocation:
    from wiki_api.pipeline.identity import IdentityAllocation

    return IdentityAllocation(
        type=EntityType.LOCATION,
        ids={key: number for number, key in enumerate(keys, 1)},
    )


def _drawn(name: str, rank: int, x: int, y: int) -> dict[str, Any]:
    return {"name": name, "rank": rank, "x": x, "y": y}


def _place(name: str, x: int, y: int, rank: int = 8) -> NamedPlace:
    return NamedPlace(key=folded(name), name=name, x=x, y=y, rank=rank)


def test_a_label_becomes_a_place_standing_at_the_tile_it_is_drawn_over(
    tmp_path: Any,
) -> None:
    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    outcome = read_map_places(staged, _allocation("lumbridge"))
    entity = outcome.read.document.entities[0]
    assert entity.name == "Lumbridge"
    assert entity.attributes["centre"] == {"x": 3222, "y": 3218, "plane": 0}
    assert "1 places" in outcome.notes[0]


def test_a_place_claims_no_tiles_that_no_source_gave_it(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [_drawn("Baxtorian Falls", 8, 2515, 3462)])
    entity = read_map_places(
        staged, _allocation("baxtorianfalls")
    ).read.document.entities[0]
    assert "bounds" not in entity.attributes


def test_every_key_the_map_lands_is_offered_for_numbering(tmp_path: Any) -> None:
    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    assert place_keys(staged) == ("lumbridge",)


def test_a_place_nobody_numbered_stops_the_build(tmp_path: Any) -> None:
    import pytest

    staged = _staged(tmp_path, [_drawn("Lumbridge", 9, 3222, 3218)])
    with pytest.raises(UnallocatedIdentity):
        read_map_places(staged, _allocation())


def test_with_nothing_staged_the_reader_invents_no_place(tmp_path: Any) -> None:
    from tests.sources import staged_from

    staged = staged_from(tmp_path, {})
    assert read_map_places(staged, _allocation()).read.document.entities == ()
    assert place_keys(staged) == ()


def test_the_same_name_drawn_twice_lands_once() -> None:
    twice = (_place("Bandit Camp", 3036, 3689), _place("Bandit Camp", 3175, 2977))
    kept = _first_of_each(twice)
    assert len(kept) == 1
    assert (kept[0].x, kept[0].y) == (3036, 3689)


def test_a_place_says_which_region_its_point_falls_in() -> None:
    expected = 2515 // 64 * 256 + 3462 // 64
    assert _place("Baxtorian Falls", 2515, 3462).region_id == expected


def test_the_attributes_carry_the_point_the_map_drew() -> None:
    told = _attributes(_place("Baxtorian Falls", 2515, 3462))
    assert told["centre"] == {"x": 2515, "y": 3462, "plane": 0}
    assert told["kind"] == LocationKind.AREA.value
