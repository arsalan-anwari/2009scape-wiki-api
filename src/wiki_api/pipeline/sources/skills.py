"""Read the staged skill tables into what a thing yields and what an item makes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import Skill, SourceKind
from wiki_api.pipeline.artifact.overlay import OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import DECLARED_CONSTANTS, DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from wiki_api.pipeline.enums.constants import Constants
    from wiki_api.pipeline.enums.reader import EnumConstant
    from wiki_api.pipeline.enums.values import EnumValue
    from wiki_api.pipeline.sources.staged import StagedSources

RESOURCES: Final = DeclaredTable(
    enum="SkillingResource", path="content/global/skill/gather/SkillingResource.java"
)
STALLS: Final = DeclaredTable(
    enum="Stall", path="content/global/skill/thieving/Stall.java"
)
COOKABLES: Final = DeclaredTable(
    enum="CookableItems", path="content/global/skill/cooking/CookableItems.java"
)
SCROLLS: Final = DeclaredTable(
    enum="SummoningScroll", path="content/global/skill/summoning/SummoningScroll.java"
)
BARS: Final = DeclaredTable(enum="Bars", path="content/global/skill/smithing/Bars.java")
BAR_TYPES: Final = DeclaredTable(
    enum="BarType", path="content/global/skill/smithing/BarType.java"
)
SMITHING_TYPES: Final = DeclaredTable(
    enum="SmithingType", path="content/global/skill/smithing/SmithingType.java"
)
SPOTS: Final = DeclaredTable(
    enum="FishingSpot", path="content/global/skill/fishing/FishingSpot.kt"
)
OPTIONS: Final = DeclaredTable(
    enum="FishingOption", path="content/global/skill/fishing/FishingOption.kt"
)
FISH: Final = DeclaredTable(enum="Fish", path="content/global/skill/fishing/Fish.kt")
GATHERED: Final = (RESOURCES, STALLS, SPOTS)
MADE: Final = (COOKABLES, SCROLLS, BARS)
SYMBOL_KEY: Final = "symbol"
ARGUMENTS_KEY: Final = "arguments"
RESPAWN_MASK: Final = 0xFFFF
RESPAWN_SHIFT: Final = 16
SKILL_PREFIX: Final = "Skills."
RENAMED_SKILLS: Final[Mapping[str, Skill]] = {"RANGE": Skill.RANGED}


@dataclass(frozen=True)
class Tables:
    """The tables one table's rows are read through, looked up by constant name."""

    constants: Constants
    rows: Mapping[str, Mapping[str, Mapping[str, Any]]]

    @classmethod
    def of(cls, staged: StagedSources, declared: Sequence[DeclaredTable]) -> Tables:
        from wiki_api.pipeline.enums.constants import Constants as Lookup

        staged_constants = [
            one for one in DECLARED_CONSTANTS if staged.has_staged(one.staged)
        ]
        return cls(
            constants=(
                staged.constants(staged_constants) if staged_constants else Lookup()
            ),
            rows={
                one.enum: {
                    constant.name: constant.values
                    for constant in staged.table(one).constants
                }
                for one in declared
                if staged.has_staged(one.staged)
            },
        )

    def row(self, table: DeclaredTable, symbol: Any) -> Mapping[str, Any]:
        """The row a `Table.CONSTANT` symbol names, or nothing when it names none."""
        name = _symbol(symbol)
        if name is None:
            return {}
        return self.rows.get(table.enum, {}).get(name.rpartition(".")[2], {})


def read_gathering(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Turn the gathering tables into what each thing in the world gives up."""
    tables = Tables.of(staged, (OPTIONS, FISH))
    return _outcome(
        staged, GATHERED, RelationshipType.YIELDS, known, tables, _gathering_edges
    )


def read_making(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Turn the recipe tables into what one item is turned into."""
    tables = Tables.of(staged, (BAR_TYPES, SMITHING_TYPES))
    return _outcome(staged, MADE, RelationshipType.MAKES, known, tables, _making_edges)


def _gathering_edges(
    tables: Tables, declared: DeclaredTable, constant: EnumConstant
) -> Iterator[dict[str, Any]]:
    if declared is RESOURCES:
        yield from _resource_edges(constant)
    elif declared is SPOTS:
        yield from _fishing_edges(tables, constant)
    else:
        yield from _stall_edges(constant)


def _fishing_edges(tables: Tables, constant: EnumConstant) -> Iterator[dict[str, Any]]:
    """One link per spot, option and fish, because the tool is part of the answer."""
    spots = [
        identity
        for identity in (
            _resolved(tables, one) for one in _listed(constant.values.get("ids"))
        )
        if identity is not None
    ]
    for option in _listed(constant.values.get("options")):
        chosen = tables.row(OPTIONS, option)
        if not chosen:
            continue
        tool = _resolved(tables, chosen.get("tool"))
        for named in _listed(chosen.get("fish")):
            caught = tables.row(FISH, named)
            item = _resolved(tables, caught.get("id"))
            if item is None:
                continue
            for spot in spots:
                yield {
                    "src": str(EntityKey(type=EntityType.NPC, id=spot)),
                    "rel": RelationshipType.YIELDS.value,
                    "dst": str(EntityKey(type=EntityType.ITEM, id=item)),
                    "attributes": {
                        "skill": Skill.FISHING.value,
                        "level": _level(caught.get("level")),
                        "experience": _decimal(caught.get("experience")),
                        "tool": tool,
                    },
                    "order_key": _level(caught.get("level")),
                    "source_ref": f"{SPOTS.filename}#{constant.name}",
                }


def _resource_edges(constant: EnumConstant) -> Iterator[dict[str, Any]]:
    values = constant.values
    reward = _identifier(values.get("reward"))
    scenery = _identifier(values.get("id"))
    skill = _skill_of(values.get("skillId"))
    if reward is None or scenery is None or skill is None:
        return
    packed = _whole(values.get("respawnRate")) or 0
    yield {
        "src": str(EntityKey(type=EntityType.SCENERY, id=scenery)),
        "rel": RelationshipType.YIELDS.value,
        "dst": str(EntityKey(type=EntityType.ITEM, id=reward)),
        "attributes": {
            "skill": skill.value,
            "level": _level(values.get("level")),
            "experience": _decimal(values.get("experience")),
            "amount": max(_whole(values.get("rewardAmount")) or 1, 1),
            "success_rate": _decimal(values.get("rate")),
            "respawn_min": packed & RESPAWN_MASK,
            "respawn_max": (packed >> RESPAWN_SHIFT) & RESPAWN_MASK,
        },
        "order_key": _level(values.get("level")),
        "source_ref": f"{RESOURCES.filename}#{constant.name}",
    }


def _stall_edges(constant: EnumConstant) -> Iterator[dict[str, Any]]:
    values = constant.values
    level = _level(values.get("level"))
    for scenery in _numbers(values.get("full_ids")):
        for item, amount in _rewards(values.get("rewards")):
            yield {
                "src": str(EntityKey(type=EntityType.SCENERY, id=scenery)),
                "rel": RelationshipType.YIELDS.value,
                "dst": str(EntityKey(type=EntityType.ITEM, id=item)),
                "attributes": {
                    "skill": Skill.THIEVING.value,
                    "level": level,
                    "experience": _decimal(values.get("experience")),
                    "amount": max(amount, 1),
                    "respawn_min": _whole(values.get("delay")),
                    "respawn_max": _whole(values.get("delay")),
                },
                "order_key": level,
                "source_ref": f"{STALLS.filename}#{constant.name}",
            }


def _making_edges(
    tables: Tables, declared: DeclaredTable, constant: EnumConstant
) -> Iterator[dict[str, Any]]:
    if declared is BARS:
        yield from _smithing_edges(tables, constant)
        return
    values = constant.values
    level = _level(values.get("level"))
    if declared is COOKABLES:
        sources, product, skill, experience = (
            _numbers(values.get("raw")),
            _identifier(values.get("cooked")),
            Skill.COOKING,
            _decimal(values.get("experience")),
        )
    else:
        sources, product, skill, experience = (
            _numbers(values.get("items")),
            _identifier(values.get("itemId")),
            Skill.SUMMONING,
            _decimal(values.get("xp")),
        )
    if product is None:
        return
    for ingredient in sources:
        yield {
            "src": str(EntityKey(type=EntityType.ITEM, id=ingredient)),
            "rel": RelationshipType.MAKES.value,
            "dst": str(EntityKey(type=EntityType.ITEM, id=product)),
            "attributes": {
                "skill": skill.value,
                "level": level,
                "experience": experience,
            },
            "order_key": level,
            "source_ref": f"{declared.filename}#{constant.name}",
        }


def _smithing_edges(tables: Tables, constant: EnumConstant) -> Iterator[dict[str, Any]]:
    values = constant.values
    bar = tables.row(BAR_TYPES, values.get("Btype"))
    shape = tables.row(SMITHING_TYPES, values.get("Stype"))
    ingredient = _identifier(bar.get("bar"))
    product = _identifier(values.get("productId"))
    if ingredient is None or product is None:
        return
    bars = max(_whole(shape.get("requiredBars")) or 1, 1)
    experience = _decimal(bar.get("experience"))
    level = _level(values.get("level"))
    yield {
        "src": str(EntityKey(type=EntityType.ITEM, id=ingredient)),
        "rel": RelationshipType.MAKES.value,
        "dst": str(EntityKey(type=EntityType.ITEM, id=product)),
        "attributes": {
            "skill": Skill.SMITHING.value,
            "level": level,
            "experience": None if experience is None else experience * bars,
            "ingredients": bars,
            "amount": max(_whole(shape.get("productedAmount")) or 1, 1),
        },
        "order_key": level,
        "source_ref": f"{BARS.filename}#{constant.name}",
    }


def _outcome(
    staged: StagedSources,
    declared_tables: Sequence[DeclaredTable],
    rel: RelationshipType,
    known: frozenset[EntityKey],
    tables: Tables,
    build: Any,
) -> SourceOutcome:
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    skipped: list[Skipped] = []
    read = 0
    for declared in declared_tables:
        if not staged.has_staged(declared.staged):
            continue
        table = staged.table(declared)
        read += len(table.constants)
        for constant in table.constants:
            for edge in build(tables, declared, constant):
                _keep(declared, edge, edges, skipped, known)
    names = ", ".join(one.enum for one in declared_tables)
    return SourceOutcome(
        source=rel.value,
        read=_document(staged, declared_tables, tuple(edges.values())),
        skipped=tuple(skipped),
        notes=(
            f"{read} constants read from {names}",
            f"{len(edges)} links written",
        ),
    )


def _keep(
    declared: DeclaredTable,
    edge: Mapping[str, Any],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    skipped: list[Skipped],
    known: frozenset[EntityKey],
) -> None:
    attributes = edge["attributes"]
    tool = attributes.get("tool") if isinstance(attributes, dict) else None
    identity = (str(edge["src"]), str(edge["dst"]), "" if tool is None else str(tool))
    missing = [
        endpoint
        for endpoint in (identity[0], identity[1])
        if EntityKey.parse(endpoint) not in known
    ]
    if missing:
        skipped.append(
            Skipped(
                source=declared.filename,
                reason=SkipReason.UNKNOWN_TARGET,
                detail=missing[0],
            )
        )
        return
    if identity in edges:
        skipped.append(
            Skipped(
                source=declared.filename,
                reason=SkipReason.ALREADY_STATED,
                detail=f"{identity[0]} {identity[1]}",
            )
        )
        return
    edges[identity] = dict(edge)


def _skill_of(value: EnumValue) -> Skill | None:
    if not isinstance(value, dict):
        return None
    symbol = value.get(SYMBOL_KEY)
    if not isinstance(symbol, str) or not symbol.startswith(SKILL_PREFIX):
        return None
    name = symbol.removeprefix(SKILL_PREFIX)
    renamed = RENAMED_SKILLS.get(name)
    if renamed is not None:
        return renamed
    found = Skill.coerce(name.lower())
    return found if isinstance(found, Skill) else None


def _rewards(value: EnumValue) -> Iterator[tuple[int, int]]:
    if not isinstance(value, list):
        return
    for entry in value:
        if not isinstance(entry, dict):
            continue
        arguments = entry.get(ARGUMENTS_KEY)
        if not isinstance(arguments, list) or not arguments:
            continue
        item = _identifier(arguments[0])
        amount = _whole(arguments[1]) if len(arguments) > 1 else 1
        if item is not None:
            yield item, amount or 1


def _symbol(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    name = value.get(SYMBOL_KEY)
    return name if isinstance(name, str) else None


def _listed(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value) if isinstance(value, list) else (value,)


def _resolved(tables: Tables, value: Any) -> int | None:
    """The id a column names, whether it wrote a number or a declared symbol."""
    number = _identifier(value)
    if number is not None:
        return number
    name = _symbol(value)
    if name is None:
        return None
    found = tables.constants.id_of(name)
    return None if found is None or found < 0 else found


def _numbers(value: EnumValue) -> tuple[int, ...]:
    if isinstance(value, list):
        read = (_identifier(entry) for entry in value)
        return tuple(number for number in read if number is not None)
    single = _identifier(value)
    return () if single is None else (single,)


def _identifier(value: EnumValue) -> int | None:
    """The id a column names, with the game's way of writing 'nothing' read as none."""
    number = _whole(value)
    return None if number is None or number < 0 else number


def _whole(value: EnumValue) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def _decimal(value: EnumValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) or None


def _level(value: EnumValue) -> int:
    level = _whole(value) or 1
    return min(max(level, 1), 99)


def _document(
    staged: StagedSources,
    tables: Sequence[DeclaredTable],
    edges: Sequence[Mapping[str, Any]],
) -> OverlaySource:
    first = tables[0]
    return OverlaySource.model_validate(
        {
            "origin": first.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CODE.value,
                "source_file": first.filename,
                "game_version": str(staged.version_of(first.staged)),
                "edges": list(edges),
            },
        }
    )


# test cases


def _table(declared: DeclaredTable, constants: list[dict[str, Any]]) -> str:
    import json

    return json.dumps(
        {
            "enum": declared.enum,
            "source_file": declared.filename,
            "language": "java",
            "columns": [],
            "constants": constants,
        }
    )


DECLARED_IN_TESTS: Final = {
    "resources": RESOURCES,
    "stalls": STALLS,
    "cookables": COOKABLES,
    "scrolls": SCROLLS,
    "bars": BARS,
    "bar_types": BAR_TYPES,
    "smithing_types": SMITHING_TYPES,
    "spots": SPOTS,
    "options": OPTIONS,
    "fish": FISH,
}


def _staged(
    tmp_path: Any,
    constants: dict[str, dict[str, int]] | None = None,
    **tables: list[dict[str, Any]],
) -> StagedSources:
    import json

    from tests.sources import staged_from

    written = {
        DECLARED_IN_TESTS[name].staged: _table(DECLARED_IN_TESTS[name], rows)
        for name, rows in tables.items()
    }
    for one in DECLARED_IN_TESTS.values():
        written.setdefault(one.staged, _table(one, []))
    for declared in DECLARED_CONSTANTS:
        written[declared.staged] = json.dumps(
            {
                "object_name": declared.object_name,
                "source_file": declared.filename,
                "ids": (constants or {}).get(declared.object_name, {}),
            }
        )
    return staged_from(tmp_path, written)


def _known(*keys: tuple[str, int]) -> frozenset[EntityKey]:
    return frozenset(
        EntityKey(type=EntityType(kind), id=number) for kind, number in keys
    )


def test_a_rock_gives_up_an_ore_at_a_level(tmp_path: Any) -> None:
    outcome = read_gathering(
        _staged(
            tmp_path,
            resources=[
                {
                    "name": "COPPER_1",
                    "values": {
                        "id": 2090,
                        "level": 1,
                        "rate": 0.25,
                        "respawnRate": 50 | 100 << 16,
                        "experience": 17.5,
                        "reward": 436,
                        "rewardAmount": 1,
                        "skillId": {"symbol": "Skills.MINING"},
                    },
                }
            ],
        ),
        _known(("scenery", 2090), ("item", 436)),
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == EntityKey(type=EntityType.SCENERY, id=2090)
    assert edge.dst == EntityKey(type=EntityType.ITEM, id=436)
    assert edge.attributes["skill"] == "mining"
    assert edge.attributes["experience"] == 17.5
    assert edge.attributes["respawn_min"] == 50
    assert edge.attributes["respawn_max"] == 100


def test_a_resource_that_gives_nothing_writes_no_link(tmp_path: Any) -> None:
    outcome = read_gathering(
        _staged(
            tmp_path,
            resources=[
                {
                    "name": "APPLE_TREE",
                    "values": {
                        "id": 7941,
                        "level": 1,
                        "reward": -1,
                        "skillId": {"symbol": "Skills.WOODCUTTING"},
                    },
                }
            ],
        ),
        _known(("scenery", 7941)),
    )
    assert outcome.read.document.edges == ()


def test_a_stall_gives_every_reward_it_lists(tmp_path: Any) -> None:
    outcome = read_gathering(
        _staged(
            tmp_path,
            stalls=[
                {
                    "name": "VEGETABLE_STALL",
                    "values": {
                        "full_ids": [4706],
                        "level": 2,
                        "experience": 10,
                        "delay": 4,
                        "rewards": [
                            {"call": "Item", "arguments": [1957, 1]},
                            {"call": "Item", "arguments": [1965, 2]},
                        ],
                    },
                }
            ],
        ),
        _known(("scenery", 4706), ("item", 1957), ("item", 1965)),
    )
    written = {edge.dst.id: edge for edge in outcome.read.document.edges}
    assert set(written) == {1957, 1965}
    assert written[1965].attributes["amount"] == 2
    assert written[1965].attributes["skill"] == "thieving"


def test_a_link_to_something_nothing_declares_is_counted(tmp_path: Any) -> None:
    outcome = read_gathering(
        _staged(
            tmp_path,
            resources=[
                {
                    "name": "COPPER_1",
                    "values": {
                        "id": 2090,
                        "level": 1,
                        "reward": 436,
                        "skillId": {"symbol": "Skills.MINING"},
                    },
                }
            ],
        ),
        _known(("scenery", 2090)),
    )
    assert outcome.read.document.edges == ()
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_one_pair_stated_twice_is_written_once(tmp_path: Any) -> None:
    values = {
        "id": 2090,
        "level": 1,
        "reward": 436,
        "skillId": {"symbol": "Skills.MINING"},
    }
    outcome = read_gathering(
        _staged(
            tmp_path,
            resources=[
                {"name": "COPPER_1", "values": values},
                {"name": "COPPER_2", "values": values},
            ],
        ),
        _known(("scenery", 2090), ("item", 436)),
    )
    assert len(outcome.read.document.edges) == 1
    assert outcome.skipped_by_reason() == {"already_stated": 1}


def test_a_raw_fish_makes_the_cooked_one(tmp_path: Any) -> None:
    outcome = read_making(
        _staged(
            tmp_path,
            cookables=[
                {
                    "name": "CHICKEN",
                    "values": {
                        "cooked": 2140,
                        "raw": 2138,
                        "burnt": 2144,
                        "level": 1,
                        "experience": 30,
                    },
                }
            ],
        ),
        _known(("item", 2138), ("item", 2140)),
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == EntityKey(type=EntityType.ITEM, id=2138)
    assert edge.dst == EntityKey(type=EntityType.ITEM, id=2140)
    assert edge.attributes["skill"] == "cooking"
    assert edge.attributes["experience"] == 30.0


def test_every_pouch_a_scroll_is_made_from_is_written(tmp_path: Any) -> None:
    outcome = read_making(
        _staged(
            tmp_path,
            scrolls=[
                {
                    "name": "HOWL_SCROLL",
                    "values": {
                        "itemId": 12425,
                        "xp": 0.1,
                        "level": 1,
                        "items": [12047, 12048],
                    },
                }
            ],
        ),
        _known(("item", 12425), ("item", 12047), ("item", 12048)),
    )
    assert {edge.src.id for edge in outcome.read.document.edges} == {12047, 12048}
    assert outcome.read.document.edges[0].attributes["skill"] == "summoning"


def test_a_bar_makes_what_it_is_smithed_into_at_the_experience_it_takes(
    tmp_path: Any,
) -> None:
    outcome = read_making(
        _staged(
            tmp_path,
            bars=[
                {
                    "name": "BRONZE_PLATEBODY",
                    "values": {
                        "Btype": {"symbol": "BarType.BRONZE"},
                        "Stype": {"symbol": "SmithingType.TYPE_PLATEBODY"},
                        "productId": 1117,
                        "level": 18,
                    },
                }
            ],
            bar_types=[
                {
                    "name": "BRONZE",
                    "values": {"bar": 2349, "experience": 12.5, "string": "Bronze"},
                }
            ],
            smithing_types=[
                {
                    "name": "TYPE_PLATEBODY",
                    "values": {"requiredBars": 5, "productedAmount": 1},
                }
            ],
        ),
        _known(("item", 2349), ("item", 1117)),
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == EntityKey(type=EntityType.ITEM, id=2349)
    assert edge.dst == EntityKey(type=EntityType.ITEM, id=1117)
    assert edge.attributes["skill"] == "smithing"
    assert edge.attributes["experience"] == 62.5
    assert edge.attributes["ingredients"] == 5


def _fishing(tmp_path: Any) -> StagedSources:
    return _staged(
        tmp_path,
        constants={
            "Items": {"SMALL_FISHING_NET_303": 303, "RAW_SHRIMPS_317": 317},
            "NPCs": {"FISHING_SPOT_952": 952},
        },
        spots=[
            {
                "name": "NET_BAIT",
                "values": {
                    "ids": [{"symbol": "NPCs.FISHING_SPOT_952"}],
                    "options": [{"symbol": "FishingOption.SMALL_NET"}],
                },
            }
        ],
        options=[
            {
                "name": "SMALL_NET",
                "values": {
                    "tool": {"symbol": "Items.SMALL_FISHING_NET_303"},
                    "level": 1,
                    "option": "net",
                    "fish": [{"symbol": "Fish.SHRIMP"}],
                },
            }
        ],
        fish=[
            {
                "name": "SHRIMP",
                "values": {
                    "id": {"symbol": "Items.RAW_SHRIMPS_317"},
                    "level": 1,
                    "experience": 10.0,
                },
            }
        ],
    )


def test_a_fishing_spot_yields_the_fish_the_tool_catches(tmp_path: Any) -> None:
    outcome = read_gathering(
        _fishing(tmp_path), _known(("npc", 952), ("item", 317), ("item", 303))
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == EntityKey(type=EntityType.NPC, id=952)
    assert edge.dst == EntityKey(type=EntityType.ITEM, id=317)
    assert edge.attributes["skill"] == "fishing"
    assert edge.attributes["experience"] == 10.0
    assert edge.attributes["tool"] == 303


def test_a_symbol_is_looked_up_rather_than_read_off_its_name(tmp_path: Any) -> None:
    outcome = read_gathering(_fishing(tmp_path), _known(("npc", 952), ("item", 317)))
    assert len(outcome.read.document.edges) == 1
    nothing = read_gathering(
        _staged(
            tmp_path,
            spots=[
                {
                    "name": "NET_BAIT",
                    "values": {
                        "ids": [{"symbol": "NPCs.FISHING_SPOT_952"}],
                        "options": [{"symbol": "FishingOption.SMALL_NET"}],
                    },
                }
            ],
        ),
        _known(("npc", 952), ("item", 317)),
    )
    assert nothing.read.document.edges == ()


def test_a_skill_the_game_spells_differently_still_lands() -> None:
    assert _skill_of({"symbol": "Skills.RANGE"}) is Skill.RANGED
    assert _skill_of({"symbol": "Skills.MINING"}) is Skill.MINING
    assert _skill_of({"symbol": "Something.ELSE"}) is None
    assert _skill_of(7) is None


def test_a_packed_respawn_reads_as_the_two_numbers_it_holds() -> None:
    packed = 50 | 100 << 16
    assert packed & RESPAWN_MASK == 50
    assert (packed >> RESPAWN_SHIFT) & RESPAWN_MASK == 100


def test_a_level_outside_the_range_a_player_can_reach_is_held_inside_it() -> None:
    assert _level(0) == 1
    assert _level(None) == 1
    assert _level(120) == 99
    assert _level(60) == 60
