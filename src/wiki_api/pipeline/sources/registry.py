"""Run every adapter over the staged sources, in the order they depend on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from wiki_api.domain.attributes import LocationAttributes
from wiki_api.domain.entity import Visibility
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.pipeline.identity import IdentityAllocation
from wiki_api.pipeline.places import Gazetteer, Place
from wiki_api.pipeline.sources import (
    ammunition,
    cache,
    drops,
    food,
    items,
    npcs,
    placements,
    places,
    prices,
    quests,
    rooms,
    scenery,
    shops,
    skills,
    slayer,
    spawns,
)
from wiki_api.pipeline.sources.overridden import overridden_by

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.artifact.overlay import OverlaySource
    from wiki_api.pipeline.sources.outcome import SourceOutcome
    from wiki_api.pipeline.sources.staged import StagedSources


READ_TABLES: Final = frozenset(
    {
        "Quests",
        "SkillingResource",
        "Stall",
        "CookableItems",
        "SummoningScroll",
        "Bars",
        "BarType",
        "SmithingType",
        "Fish",
        "FishingSpot",
        "FishingOption",
        "Tasks",
        "Master",
        "RoomProperties",
        "Consumables",
        "WeaponInterfaces",
    }
)
DUPLICATE_TABLES: Final[Mapping[str, str]] = {
    "SkillingTool": (
        "12 of its 16 numeric-id tools already carry the same requirement on the item, "
        "and the other 4 are level 1"
    )
}


def unread_tables() -> tuple[str, ...]:
    """The enum tables staging writes that no adapter turns into facts yet."""
    from wiki_api.pipeline.staging.declared import DECLARED_TABLES

    return tuple(
        sorted(
            declared.enum
            for declared in DECLARED_TABLES
            if declared.enum not in READ_TABLES
            and declared.enum not in DUPLICATE_TABLES
        )
    )


def duplicate_tables() -> tuple[str, ...]:
    """The tables nothing reads because the artifact already holds what they say."""
    return tuple(
        f"{name}: {reason}" for name, reason in sorted(DUPLICATE_TABLES.items())
    )


def read_sources(
    staged: StagedSources,
    overlays: Sequence[OverlaySource],
    allocations: Mapping[EntityType, IdentityAllocation] | None = None,
) -> tuple[SourceOutcome, ...]:
    """Read the staged sources into documents, letting overlays own what they define."""
    overridden = overridden_by(overlays)
    given = allocations or {}
    described = [
        items.read_items(staged, overridden),
        npcs.read_npcs(staged, overridden),
        shops.read_shops(staged, overridden),
        quests.read_quests(staged, _allocated(given, EntityType.QUEST), overridden),
        scenery.read_scenery(staged, overridden),
        slayer.read_tasks(staged, _allocated(given, EntityType.TASK)),
        places.read_map_places(staged, _allocated(given, EntityType.LOCATION)),
        places.read_agreed_places(staged, _allocated(given, EntityType.LOCATION)),
        rooms.read_rooms(staged, _allocated(given, EntityType.ROOM)),
    ]
    known = overridden | _keys(described)
    extents = places_in([outcome.read for outcome in described] + list(overlays))
    named_quests = _named(described, EntityType.QUEST)
    described.extend(
        [
            cache.read_cache_items(staged, known),
            cache.read_cache_npcs(staged, known),
            cache.read_cache_quests(staged, named_quests),
            food.read_food(staged, known),
            quests.read_quest_gates(staged, _allocated(given, EntityType.QUEST), known),
            drops.read_drops(staged, known),
            shops.read_shop_edges(staged, known, overridden, cache.item_values(staged)),
            ammunition.read_ammunition(staged, known),
            spawns.read_npc_spawns(staged, known, extents),
            spawns.read_ground_spawns(staged, known, extents),
            placements.read_standing(staged, known, extents),
            skills.read_gathering(staged, known),
            skills.read_making(staged, known),
            slayer.read_slayer_edges(staged, known, _keyed(described, EntityType.TASK)),
            prices.read_prices(staged, known),
        ]
    )
    overridden.unmet()
    return tuple(described)


def _allocated(
    given: Mapping[EntityType, IdentityAllocation], entity_type: EntityType
) -> IdentityAllocation:
    return given.get(entity_type) or IdentityAllocation(type=entity_type)


def _named(
    outcomes: Sequence[SourceOutcome], entity_type: EntityType
) -> dict[str, EntityKey]:
    """Every entity of one type keyed by its name, for a source that has only a name."""
    return {
        entity.name: entity.key
        for outcome in outcomes
        for entity in outcome.read.document.entities
        if entity.type is entity_type and entity.name
    }


def _keyed(
    outcomes: Sequence[SourceOutcome], entity_type: EntityType
) -> dict[str, EntityKey]:
    """Every entity of one type keyed by the natural token the source calls it."""
    return {
        entity.source_key: entity.key
        for outcome in outcomes
        for entity in outcome.read.document.entities
        if entity.type is entity_type and entity.source_key
    }


def places_in(sources: Sequence[OverlaySource]) -> Gazetteer:
    """Every place a tile can be said to be in, by its tiles or by its point."""
    found: list[Place] = []
    for overlay in sources:
        for entity in overlay.document.entities:
            if entity.type is not EntityType.LOCATION:
                continue
            if entity.visibility is Visibility.HIDDEN:
                continue
            told = LocationAttributes.model_validate(entity.attributes)
            if told.bounds is None and told.centre is None:
                continue
            found.append(Place(key=entity.key, bounds=told.bounds, centre=told.centre))
    return Gazetteer(found)


def _keys(outcomes: Sequence[SourceOutcome]) -> frozenset[EntityKey]:
    return frozenset(
        entity.key for outcome in outcomes for entity in outcome.read.document.entities
    )


# test cases


def _overlay(*entities: object) -> OverlaySource:
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    return OverlaySource.model_validate(
        {
            "origin": "overlays/places.json",
            "document": {
                "schema": 1,
                "source": "overlay",
                "game_version": "test",
                "precedence": 10,
                "entities": list(entities),
            },
        }
    )


def test_the_tables_no_adapter_reads_are_named_rather_than_forgotten() -> None:
    unread = unread_tables()
    assert "Quests" not in unread
    assert "SkillingResource" not in unread
    assert "Master" not in unread
    assert "RoomProperties" not in unread


def test_a_table_the_artifact_already_says_is_named_as_a_duplicate() -> None:
    assert "SkillingTool" not in unread_tables()
    assert any(one.startswith("SkillingTool:") for one in duplicate_tables())


def test_what_an_overlay_defines_is_what_an_adapter_leaves_alone() -> None:
    overlays = [_overlay({"type": "item", "id": 14422, "name": "Scroll"})]
    assert overridden_by(overlays).keys == {EntityKey(type=EntityType.ITEM, id=14422)}


def test_a_patch_does_not_take_a_definition_away_from_a_source() -> None:
    overlays = [_overlay({"type": "item", "id": 4587, "mode": "patch", "name": "X"})]
    assert overridden_by(overlays).keys == frozenset()


def test_a_place_with_an_extent_is_somewhere_a_spawn_can_land() -> None:
    overlays = [
        _overlay(
            {
                "type": "location",
                "id": 1,
                "name": "Wilderness",
                "attributes": {
                    "bounds": {
                        "min_x": 2944,
                        "min_y": 3525,
                        "max_x": 3392,
                        "max_y": 3968,
                    }
                },
            }
        )
    ]
    from wiki_api.domain.space import Coordinate

    places = places_in(overlays)
    assert len(places) == 1
    assert places.holding(Coordinate(x=3000, y=3600)) == EntityKey(
        type=EntityType.LOCATION, id=1
    )


def test_a_place_with_no_extent_holds_nothing() -> None:
    overlays = [_overlay({"type": "location", "id": 1, "name": "Burthorpe"})]
    assert len(places_in(overlays)) == 0


def test_a_place_nobody_publishes_holds_nothing() -> None:
    overlays = [
        _overlay(
            {
                "type": "location",
                "id": 1,
                "name": "Nowhere",
                "visibility": "hidden",
                "attributes": {
                    "bounds": {"min_x": 1, "min_y": 1, "max_x": 9, "max_y": 9}
                },
            }
        )
    ]
    assert len(places_in(overlays)) == 0
