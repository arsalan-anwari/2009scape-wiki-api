"""Run every adapter over the staged sources, in the order they depend on."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from wiki_api.domain.attributes import LocationAttributes
from wiki_api.domain.entity import Visibility
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.pipeline.identity import IdentityAllocation
from wiki_api.pipeline.sources import (
    ammunition,
    cache,
    drops,
    items,
    npcs,
    prices,
    quests,
    shops,
    spawns,
)
from wiki_api.pipeline.sources.spawns import Place, Places

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.pipeline.artifact.overlay import OverlaySource
    from wiki_api.pipeline.sources.outcome import SourceOutcome
    from wiki_api.pipeline.sources.staged import StagedSources


READ_TABLES: Final = frozenset({"Quests"})


def unread_tables() -> tuple[str, ...]:
    """The enum tables staging writes that no adapter turns into facts yet."""
    from wiki_api.pipeline.staging.declared import DECLARED_TABLES

    return tuple(
        sorted(
            declared.enum
            for declared in DECLARED_TABLES
            if declared.enum not in READ_TABLES
        )
    )


def read_sources(
    staged: StagedSources,
    overlays: Sequence[OverlaySource],
    allocations: IdentityAllocation | None = None,
) -> tuple[SourceOutcome, ...]:
    """Read the staged sources into documents, letting overlays own what they define."""
    overridden = defined_by(overlays)
    quest_ids = allocations or IdentityAllocation(type=EntityType.QUEST)
    described = [
        items.read_items(staged, overridden),
        npcs.read_npcs(staged, overridden),
        shops.read_shops(staged, overridden),
        quests.read_quests(staged, quest_ids, overridden),
    ]
    known = overridden | _keys(described)
    places = places_in(overlays)
    described.extend(
        [
            cache.read_cache_items(staged, known),
            cache.read_cache_npcs(staged, known),
            drops.read_drops(staged, known),
            shops.read_shop_edges(staged, known, overridden, cache.item_values(staged)),
            ammunition.read_ammunition(staged, known),
            spawns.read_npc_spawns(staged, known, places),
            spawns.read_ground_spawns(staged, known, places),
            prices.read_prices(staged, known),
        ]
    )
    return tuple(described)


def defined_by(overlays: Sequence[OverlaySource]) -> frozenset[EntityKey]:
    """The entities the hand-written overlays define, which no adapter may restate."""
    from wiki_api.pipeline.artifact.overlay import OverlayMode

    return frozenset(
        entity.key
        for overlay in overlays
        for entity in overlay.document.entities
        if entity.mode is OverlayMode.DEFINE
    )


def places_in(overlays: Sequence[OverlaySource]) -> Places:
    """The places an overlay gave an extent to, which is what a spawn can land in."""
    found: list[Place] = []
    for overlay in overlays:
        for entity in overlay.document.entities:
            if entity.type is not EntityType.LOCATION:
                continue
            if entity.visibility is Visibility.HIDDEN:
                continue
            bounds = LocationAttributes.model_validate(entity.attributes).bounds
            if bounds is not None:
                found.append(Place(key=entity.key, bounds=bounds))
    return Places(found)


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
    assert "SkillingResource" in unread
    assert "Stall" in unread


def test_what_an_overlay_defines_is_what_an_adapter_leaves_alone() -> None:
    overlays = [_overlay({"type": "item", "id": 14422, "name": "Scroll"})]
    assert defined_by(overlays) == {EntityKey(type=EntityType.ITEM, id=14422)}


def test_a_patch_does_not_take_a_definition_away_from_a_source() -> None:
    overlays = [_overlay({"type": "item", "id": 4587, "mode": "patch", "name": "X"})]
    assert defined_by(overlays) == frozenset()


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
