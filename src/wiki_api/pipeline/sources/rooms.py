"""Read the construction table into the rooms a player can build."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.errors import UnallocatedIdentity
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.enums.reader import EnumConstant
    from wiki_api.pipeline.identity import IdentityAllocation
    from wiki_api.pipeline.sources.staged import StagedSources

ROOMS: Final = DeclaredTable(
    enum="RoomProperties",
    path="content/global/skill/construction/RoomProperties.java",
)
LEVEL_FIELD: Final = "level"
COST_FIELD: Final = "cost"
LAYOUT_FIELD: Final = "configuration"
HOTSPOT_FIELD: Final = "hotspots"
SYMBOL_KEY: Final = "symbol"
OUTDOORS: Final = "Room.LAND"
WORD_SEPARATOR: Final = "_"
MAX_LEVEL: Final = 99


def room_keys(staged: StagedSources) -> tuple[str, ...]:
    """The natural keys the construction table declares, in its own order."""
    if not staged.has_staged(ROOMS.staged):
        return ()
    return tuple(constant.name for constant in staged.table(ROOMS).constants)


def read_rooms(staged: StagedSources, allocation: IdentityAllocation) -> SourceOutcome:
    """Turn every declared room into an entity, numbered by the allocation."""
    constants = _constants(staged)
    entities = []
    for constant in constants:
        room_id = allocation.id_of(constant.name)
        if room_id is None:
            raise UnallocatedIdentity(EntityType.ROOM.value, constant.name)
        entities.append(
            {
                "type": EntityType.ROOM.value,
                "id": room_id,
                "name": _readable(constant.name),
                "source_key": constant.name,
                "source_ref": f"{ROOMS.filename}#{constant.name}",
                "attributes": _attributes(constant),
            }
        )
    return SourceOutcome(
        source=ROOMS.filename,
        read=_document(staged, entities),
        notes=(f"{len(constants)} rooms declared",),
    )


def _constants(staged: StagedSources) -> tuple[EnumConstant, ...]:
    if not staged.has_staged(ROOMS.staged):
        return ()
    return tuple(staged.table(ROOMS).constants)


def _attributes(constant: EnumConstant) -> Mapping[str, Any]:
    arguments = constant.values
    found: dict[str, Any] = {}
    level = _level(arguments.get(LEVEL_FIELD))
    if level is not None:
        found["level"] = level
    cost = arguments.get(COST_FIELD)
    if isinstance(cost, int) and not isinstance(cost, bool) and cost >= 0:
        found["build_cost"] = cost
    outdoors = _outdoors(arguments.get(LAYOUT_FIELD))
    if outdoors is not None:
        found["outdoors"] = outdoors
    spots = arguments.get(HOTSPOT_FIELD)
    if isinstance(spots, list):
        found["hotspots"] = len(spots)
    return found


def _level(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= MAX_LEVEL else None


def _outdoors(value: Any) -> bool | None:
    if not isinstance(value, dict):
        return None
    symbol = value.get(SYMBOL_KEY)
    return symbol == OUTDOORS if isinstance(symbol, str) else None


def _readable(name: str) -> str:
    """Say a constant the way a player would: `DINING_ROOM` is a dining room."""
    words = name.split(WORD_SEPARATOR)
    return " ".join([words[0].capitalize(), *(word.lower() for word in words[1:])])


def _document(
    staged: StagedSources, entities: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": ROOMS.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CODE.value,
                "source_file": ROOMS.filename,
                "game_version": str(staged.version_of(ROOMS.staged)),
                "entities": list(entities),
            },
        }
    )


# test cases


def _constant(**arguments: object) -> EnumConstant:
    from wiki_api.pipeline.enums.reader import EnumConstant

    return EnumConstant.model_validate({"name": "DINING_ROOM", "values": arguments})


def test_a_room_says_what_it_costs_and_what_it_needs() -> None:
    found = _attributes(_constant(cost=5000, level=10))
    assert found == {"build_cost": 5000, "level": 10}


def test_a_room_open_to_the_sky_says_so() -> None:
    inside = _attributes(_constant(configuration={"symbol": "Room.CHAMBER"}))
    outside = _attributes(_constant(configuration={"symbol": "Room.LAND"}))
    assert inside["outdoors"] is False
    assert outside["outdoors"] is True


def test_the_build_spots_are_counted_rather_than_listed() -> None:
    found = _attributes(_constant(hotspots=[{"call": "Hotspot"}] * 17))
    assert found["hotspots"] == 17


def test_a_level_the_game_could_never_ask_for_is_not_recorded() -> None:
    assert "level" not in _attributes(_constant(level=0))
    assert "level" not in _attributes(_constant(level=120))


def test_a_room_that_states_nothing_records_nothing() -> None:
    assert _attributes(_constant()) == {}


def test_a_constant_is_said_the_way_a_player_would_say_it() -> None:
    assert _readable("DINING_ROOM") == "Dining room"
    assert _readable("PARLOUR") == "Parlour"
    assert _readable("SUPERIOR_GARDEN") == "Superior garden"
