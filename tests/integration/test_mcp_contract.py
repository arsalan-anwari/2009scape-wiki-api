from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from fastmcp.client import Client

from wiki_api.core import BLOCK_PAGE_SIZE, Direction, Found, KnowledgeService
from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RELATIONSHIP_SPECS, RelationshipType
from wiki_api.repository.factory import open_repository
from wiki_api.surfaces.mcp import (
    CLOSE_NAMES_TOOL,
    MOST_RESULT_CHARS,
    SERVER_NAME,
    SORTS_TOOL,
    WRITTEN_TOOLS,
    create_server,
    followable,
)
from wiki_api.surfaces.mcp.answers import Outcome
from wiki_api.surfaces.mcp.naming import COMPARE_TOOL, MOVEMENT_TOOL

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from fastapi.testclient import TestClient
    from mcp.types import Tool

    from wiki_api.config import Settings
    from wiki_api.core import Named, PageDescriptor

DRAGON = "King Black Dragon"
SCIMITAR = "Dragon scimitar"
BANSHEE = "Banshee"
STOCKED = "Wooden stock"
RETIRED_NAME = "dragon-scimmy"
UNNAMED_NPC = "npc:3089"


def _run[T](work: Callable[[], Awaitable[T]]) -> T:
    return anyio.run(work)


def _called(
    settings: Settings, tool: str, arguments: Mapping[str, Any]
) -> dict[str, Any]:
    async def call() -> dict[str, Any]:
        async with Client(create_server(settings)) as client:
            answered = await client.call_tool(tool, dict(arguments))
            content: dict[str, Any] | None = answered.structured_content
            assert content is not None
            return content

    return _run(call)


def _recorded_labels(page: Named[PageDescriptor]) -> set[str]:
    described = page.resolution
    assert isinstance(described, Found)
    descriptor = described.value
    values = list(descriptor.infobox)
    for section in descriptor.sections:
        values.extend(section.attributes)
    return {value.label for value in values}


def _listed(settings: Settings) -> list[Tool]:
    async def call() -> list[Tool]:
        async with Client(create_server(settings)) as client:
            offered: list[Tool] = await client.list_tools()
            return offered

    return _run(call)


@pytest.fixture
def mcp_settings(http_settings: Settings) -> Settings:
    return http_settings


@pytest.fixture
def tools(mcp_settings: Settings) -> dict[str, Tool]:
    return {tool.name: tool for tool in _listed(mcp_settings)}


# the tool surface is derived, never written down


def _held(settings: Settings) -> frozenset[RelationshipType]:
    from wiki_api.core import KnowledgeService
    from wiki_api.repository.factory import open_repository

    repository = open_repository(settings.artifact_path)
    try:
        return KnowledgeService(repository).answerable()
    finally:
        repository.close()


def test_the_tools_offered_are_computed_from_the_registry(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    expected = set(WRITTEN_TOOLS) | {
        followed.name for followed in followable(_held(mcp_settings))
    }
    assert set(tools) == expected


def test_a_relationship_the_registry_adds_would_add_a_tool(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    offered = set(tools) - set(WRITTEN_TOOLS)
    assert len(offered) == len(_held(mcp_settings)) * len(Direction)


def test_every_relationship_is_reachable_in_both_directions(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    for followed in followable(_held(mcp_settings)):
        assert followed.name in tools


def test_this_build_can_follow_every_link_it_declares(
    mcp_settings: Settings,
) -> None:
    assert _held(mcp_settings) == frozenset(RELATIONSHIP_SPECS)


def test_a_link_with_no_edges_is_never_offered_as_a_tool(
    tools: dict[str, Tool],
) -> None:
    without = frozenset(RELATIONSHIP_SPECS) - {RelationshipType.DROPS}
    offered = {followed.name for followed in followable(without)}
    assert set(tools) - set(WRITTEN_TOOLS) - offered == {"drops", "dropped_by"}


def test_a_generated_tool_does_not_repeat_a_shape_every_other_one_states(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    for followed in followable(_held(mcp_settings)):
        assert tools[followed.name].outputSchema is None


def test_a_written_tool_states_the_shape_only_it_answers_with(
    tools: dict[str, Tool],
) -> None:
    for name in ("get_thing", "search", "list_sorts"):
        assert tools[name].outputSchema is not None


def test_the_whole_surface_costs_less_than_a_single_answer_may(
    tools: dict[str, Tool],
) -> None:
    import json

    surface = json.dumps([tool.model_dump(mode="json") for tool in tools.values()])
    assert len(surface) < MOST_RESULT_CHARS * 2


def test_no_shape_is_stated_twice_across_the_whole_surface(
    tools: dict[str, Tool],
) -> None:
    import json

    stated = [
        json.dumps(tool.outputSchema, sort_keys=True)
        for tool in tools.values()
        if tool.outputSchema is not None
    ]
    assert len(set(stated)) == len(stated)


def test_a_generated_tool_says_what_an_argument_is_in_fewer_words(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    written = tools["get_thing"].inputSchema["properties"]["name"]["description"]
    for followed in followable(_held(mcp_settings)):
        said = tools[followed.name].inputSchema["properties"]["name"]["description"]
        assert said
        assert len(said) < len(written)


def test_an_argument_a_generated_tool_repeats_is_never_the_long_way_round(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    """Only the arguments every generated tool carries are measured: one a few tools
    take for their own reasons is information, not repetition.
    """
    followed = followable(_held(mcp_settings))
    shared = ("name", "offset")
    repeated = sum(
        len(json.dumps(tools[one.name].inputSchema["properties"][argument]))
        for one in followed
        for argument in shared
    )
    assert repeated < len(followed) * 200


def test_a_walk_is_narrowed_only_where_it_answers_with_several_sorts(
    tools: dict[str, Tool], mcp_settings: Settings
) -> None:
    """The narrowing argument inlines the whole vocabulary of sorts, so offering it
    on a link that answers with one sort would buy nothing and cost every reader.
    """
    for followed in followable(_held(mcp_settings)):
        narrowed = "type" in tools[followed.name].inputSchema["properties"]
        assert narrowed is followed.is_mixed


def test_a_narrowed_walk_answers_with_one_sort_and_counts_only_that_sort(
    mcp_settings: Settings,
) -> None:
    mixed = next(
        followed
        for followed in followable(_held(mcp_settings))
        if followed.is_mixed and followed.name == "found_here"
    )
    whole = _called(mcp_settings, mixed.name, {"name": "White Wolf Mountain"})
    narrowed = _called(
        mcp_settings,
        mixed.name,
        {"name": "White Wolf Mountain", "type": EntityType.SHOP.value},
    )
    kept = narrowed["result"]["neighbours"]
    assert {row["type"] for row in kept} == {EntityType.SHOP.value}
    assert narrowed["result"]["total"] == len(kept)
    assert narrowed["result"]["total"] < whole["result"]["total"]


def test_an_answer_writes_down_no_field_holding_nothing(
    mcp_settings: Settings,
) -> None:
    from wiki_api.surfaces.mcp.projection import says_nothing

    for tool, arguments in (
        ("get_thing", {"name": SCIMITAR}),
        ("search", {"words": "dragon"}),
        ("drops", {"name": DRAGON}),
    ):
        answered = _called(mcp_settings, tool, arguments)
        assert not [key for key, value in answered.items() if says_nothing(value)]


def test_a_thing_reads_no_more_of_a_link_than_it_shows(
    mcp_settings: Settings,
) -> None:
    from wiki_api.surfaces.mcp.projection import MOST_EXAMPLES

    answered = _called(mcp_settings, "get_thing", {"name": DRAGON})
    onwards = answered["result"]["reachable"]
    assert onwards
    for one in onwards:
        assert len(one.get("examples", [])) <= MOST_EXAMPLES


def test_a_shrunk_answer_conforms_to_the_shape_its_tool_declares(
    mcp_settings: Settings,
) -> None:
    from wiki_api.surfaces.mcp.answers import Answer
    from wiki_api.surfaces.mcp.projection import Matches, Thing

    read = Answer[Thing].model_validate(
        _called(mcp_settings, "get_thing", {"name": SCIMITAR})
    )
    assert read.result is not None
    assert read.result.name == SCIMITAR
    found = Matches.model_validate(_called(mcp_settings, "search", {"words": "dragon"}))
    assert found.total >= 1


def test_a_shape_a_reader_is_quoted_needs_no_second_lookup(
    tools: dict[str, Tool],
) -> None:
    for tool in tools.values():
        if tool.outputSchema is None:
            continue
        assert "$ref" not in json.dumps(tool.outputSchema)
        assert "$defs" not in tool.outputSchema


def test_the_server_names_itself_for_whoever_connects(mcp_settings: Settings) -> None:
    async def call() -> str | None:
        async with Client(create_server(mcp_settings)) as client:
            result = client.initialize_result
            assert result is not None
            said: str | None = result.instructions
            return said

    instructions = _run(call)
    assert instructions
    assert SERVER_NAME


# every tool explains itself to whoever reads it


def test_every_tool_says_what_it_is_for(tools: dict[str, Tool]) -> None:
    for tool in tools.values():
        assert tool.description
        assert len(tool.description) > 40


def test_every_argument_is_documented(tools: dict[str, Tool]) -> None:
    for tool in tools.values():
        for name, declared in tool.inputSchema.get("properties", {}).items():
            assert declared.get("description"), f"{tool.name}.{name}"


def test_no_two_tools_read_the_same(tools: dict[str, Tool]) -> None:
    described = [tool.description for tool in tools.values()]
    assert len(set(described)) == len(described)


def test_no_tool_description_swallows_another(tools: dict[str, Tool]) -> None:
    described = {name: (tool.description or "") for name, tool in tools.items()}
    for name, words in described.items():
        for other, theirs in described.items():
            if name == other:
                continue
            assert words not in theirs, f"{name} is contained in {other}"


def test_every_answer_is_read_only_and_says_so(tools: dict[str, Tool]) -> None:
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is False


def test_every_tool_declares_what_it_will_not_exceed(tools: dict[str, Tool]) -> None:
    for tool in tools.values():
        assert tool.meta is not None
        assert tool.meta["anthropic/maxResultSizeChars"] == MOST_RESULT_CHARS


def test_nothing_may_be_written_through_these_tools(tools: dict[str, Tool]) -> None:
    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.destructiveHint in (None, False)


# the questions this phase has to be able to answer, one call each


def test_what_is_this_item(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": SCIMITAR})
    assert answered["outcome"] == Outcome.FOUND
    assert answered["result"]["name"] == SCIMITAR
    assert answered["result"]["type"] == EntityType.ITEM


def test_what_are_the_stats_of_this_npc(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": DRAGON})
    assert answered["result"]["facts"]


def test_a_thing_answers_with_every_value_it_records(
    mcp_settings: Settings,
) -> None:
    """Anything but the few worth a hover used to be dropped here, so a reader was
    told the wiki holds nothing it had not been shown.
    """
    service = KnowledgeService(open_repository(mcp_settings.artifact_path))
    for name in (SCIMITAR, DRAGON, BANSHEE):
        answered = _called(mcp_settings, "get_thing", {"name": name})
        page = service.page_by_name(name)
        recorded = _recorded_labels(page)
        assert recorded
        assert set(answered["result"]["facts"]) == recorded


def test_a_value_the_registry_marks_for_no_hover_still_reaches_a_reader(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": BANSHEE})
    said = " ".join(answered["result"]["facts"].values())
    assert "earmuffs" in said


def test_a_packed_value_names_its_parts_and_cuts_none_of_them(
    mcp_settings: Settings,
) -> None:
    """The strength bonus is eleventh of fifteen, which the run of parts used to cut
    in silence on every weapon in the game.
    """
    from wiki_api.domain.attributes import ATTRIBUTE_SPECS
    from wiki_api.domain.vocabulary import AttributeFormat

    packed = next(
        spec
        for spec in ATTRIBUTE_SPECS[EntityType.ITEM]
        if spec.format is AttributeFormat.BONUSES
    )
    answered = _called(mcp_settings, "get_thing", {"name": SCIMITAR})
    written = answered["result"]["facts"][packed.label]
    for part in packed.fields:
        assert part.label in written


def test_what_is_this_item_worth(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": SCIMITAR})
    assert answered["result"]["facts"]["Market price"] == "108590"


def test_which_items_does_this_npc_drop(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "drops", {"name": DRAGON})
    assert answered["outcome"] == Outcome.FOUND
    assert answered["result"]["total"] >= 1
    assert answered["result"]["neighbours"][0]["type"] == EntityType.ITEM


def test_which_npcs_drop_this_item(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "dropped_by", {"name": "Dragon bones"})
    assert answered["result"]["neighbours"][0]["name"] == DRAGON


def test_what_does_this_shop_sell(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "sells", {"name": "Crossbow Shop"})
    assert answered["result"]["total"] >= 1


def test_which_shops_sell_this_item(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "sold_in", {"name": STOCKED})
    assert answered["result"]["neighbours"][0]["type"] == EntityType.SHOP


def test_where_is_this_on_the_map(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "found_in", {"name": DRAGON})
    assert answered["result"]["neighbours"][0]["type"] == EntityType.LOCATION


def test_what_is_at_this_place(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "found_here", {"name": "King Black Dragon Lair"})
    assert answered["result"]["total"] >= 1


def test_what_does_working_this_thing_give(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "yields", {"name": "Tree"})
    assert answered["outcome"] == Outcome.FOUND
    assert answered["result"]["neighbours"][0]["name"] == "Logs"


def test_where_does_this_item_come_from(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "gathered_from", {"name": "Logs"})
    assert answered["result"]["neighbours"][0]["type"] == EntityType.SCENERY


def test_what_can_this_item_be_turned_into(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "makes", {"name": "Logs"})
    assert answered["result"]["total"] >= 1


def test_what_does_this_quest_reward(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "rewards", {"name": "Death Plateau"})
    assert answered["result"]["total"] >= 1


def test_what_is_this_thing_called_roughly(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "search", {"words": "dragon"})
    assert answered["total"] >= 1
    assert answered["found"][0]["name"]


def test_which_things_of_a_sort_exist(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "list_things", {"type": EntityType.QUEST.value})
    assert answered["total"] >= 1


def test_which_build_am_i_reading(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "about", {})
    assert answered["data_version"] == "fixture-0001"
    assert answered["schema_version"]


def test_which_of_these_hold_more_than_a_number(mcp_settings: Settings) -> None:
    answered = _called(
        mcp_settings,
        COMPARE_TOOL,
        {
            "type": EntityType.ITEM,
            "holds": "Strength bonus",
            "how": "more_than",
            "number": 10,
        },
    )
    assert answered["outcome"] == Outcome.FOUND
    assert [found["name"] for found in answered["result"]["found"]] == [SCIMITAR]
    facts = answered["result"]["found"][0]["facts"]
    assert facts["Strength bonus"] == "66"
    assert facts["Equipment slot"] == "weapon"


def test_which_of_these_is_the_largest(mcp_settings: Settings) -> None:
    answered = _called(
        mcp_settings,
        COMPARE_TOOL,
        {"type": EntityType.ITEM, "ordered_by": "Weight", "descending": True},
    )
    assert answered["result"]["found"][0]["name"] == "Kbd heads"
    assert answered["result"]["found"][0]["facts"]["Weight"] == "10 kg"


def test_how_many_things_one_name_answers_to_is_one_call(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings,
        COMPARE_TOOL,
        {"type": EntityType.ITEM, "named": SCIMITAR},
    )
    assert answered["outcome"] == Outcome.FOUND
    assert answered["result"]["total"] == 1
    assert [found["name"] for found in answered["result"]["found"]] == [SCIMITAR]


def test_words_no_value_answers_to_are_answered_with_the_ones_that_do(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings, COMPARE_TOOL, {"type": EntityType.ITEM, "holds": "how shiny"}
    )
    assert answered["outcome"] == Outcome.UNKNOWN
    assert "result" not in answered
    assert "Buy limit" in (answered["note"] or "")


def test_naming_nothing_to_compare_is_answered_rather_than_listed(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, COMPARE_TOOL, {"type": EntityType.ITEM})
    assert answered["outcome"] == Outcome.UNKNOWN
    assert "result" not in answered


def test_which_way_has_this_price_gone(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, MOVEMENT_TOOL, {"name": SCIMITAR})
    assert answered["outcome"] == Outcome.FOUND
    went = answered["result"]
    assert went["of"] == SCIMITAR
    assert went["went"] in {"up", "down", "nowhere"}
    assert went["opened_on"] < went["closed_on"]
    assert went["readings"] >= 1
    assert went["trust"]


def test_a_price_is_only_read_over_the_stretch_that_was_asked_for(
    mcp_settings: Settings,
) -> None:
    whole = _called(mcp_settings, MOVEMENT_TOOL, {"name": SCIMITAR})
    part = _called(
        mcp_settings, MOVEMENT_TOOL, {"name": SCIMITAR, "since": "2024-06-15"}
    )
    assert part["result"]["readings"] < whole["result"]["readings"]
    assert part["result"]["opened_on"] >= "2024-06-15"


def test_a_day_nobody_could_read_is_treated_as_no_day_at_all(
    mcp_settings: Settings,
) -> None:
    whole = _called(mcp_settings, MOVEMENT_TOOL, {"name": SCIMITAR})
    nonsense = _called(
        mcp_settings, MOVEMENT_TOOL, {"name": SCIMITAR, "since": "last tuesday"}
    )
    assert nonsense["result"]["readings"] == whole["result"]["readings"]


def test_something_the_market_never_recorded_says_so_rather_than_guessing(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, MOVEMENT_TOOL, {"name": "Ashes"})
    assert answered["outcome"] == Outcome.FOUND
    assert "result" not in answered
    assert answered["note"]


# a name is enough, and an identity still works


def test_a_name_alone_answers_without_anyone_knowing_an_id(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": "king black dragon"})
    assert answered["result"]["ref"] == "npc:50"


def test_an_identity_a_caller_already_knows_is_taken_at_its_word(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": "item:4587"})
    assert answered["result"]["name"] == SCIMITAR


def test_narrowing_to_one_sort_lets_a_bare_number_identify_something(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings, "get_thing", {"name": "4587", "type": EntityType.ITEM.value}
    )
    assert answered["result"]["name"] == SCIMITAR


# absence is an answer, never an error


def test_a_name_nothing_answers_to_comes_back_as_an_answer(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": "zzzz nothing zzzz"})
    assert answered["outcome"] == Outcome.UNKNOWN
    assert "result" not in answered
    assert answered["note"]


def test_a_retired_name_still_reaches_the_thing_it_used_to_mean(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": RETIRED_NAME})
    assert answered["outcome"] == Outcome.FOUND
    assert answered["result"]["name"] == SCIMITAR
    assert answered["result"]["ref"] == "item:4587"


def test_something_withheld_says_so_without_naming_it(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": UNNAMED_NPC})
    assert answered["outcome"] == Outcome.WITHHELD
    assert "3089" not in json.dumps(answered["note"])


def test_absence_reaches_a_walk_the_same_way_it_reaches_a_thing(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "drops", {"name": "zzzz nothing zzzz"})
    assert answered["outcome"] == Outcome.UNKNOWN
    assert "result" not in answered


def test_a_near_miss_offers_the_names_that_were_close(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": "dragon"})
    assert answered["outcome"] == Outcome.FOUND
    assert answered["others"]


# a misspelling is answered with candidates, and only a person chooses between them


def test_a_name_nothing_answers_to_is_told_where_close_spellings_come_from(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, "get_thing", {"name": "zzzz nothing zzzz"})
    assert CLOSE_NAMES_TOOL in answered["note"]
    assert SORTS_TOOL in answered["note"]


def test_what_sorts_of_thing_can_i_ask_about(mcp_settings: Settings) -> None:
    answered = _called(mcp_settings, SORTS_TOOL, {})
    listed = {sort["type"]: sort for sort in answered["sorts"]}
    assert set(listed) == {entity_type.value for entity_type in EntityType}
    assert listed["item"]["total"] >= 1
    assert listed["npc"]["plural"] == "NPCs"


def test_the_sorts_answer_carries_none_of_what_a_sort_declares(
    mcp_settings: Settings,
) -> None:
    answered = _called(mcp_settings, SORTS_TOOL, {})
    for sort in answered["sorts"]:
        assert set(sort) == {"type", "label", "plural", "total"}


def test_what_did_i_mean_by_this_misspelling(mcp_settings: Settings) -> None:
    answered = _called(
        mcp_settings,
        CLOSE_NAMES_TOOL,
        {"name": "dragon scimtar", "type": EntityType.ITEM.value},
    )
    assert [found["name"] for found in answered["found"]] == [SCIMITAR]


def test_close_names_carry_nothing_that_could_be_answered_from(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings,
        CLOSE_NAMES_TOOL,
        {"name": "dragon scimtar", "type": EntityType.ITEM.value},
    )
    assert answered["found"]
    for found in answered["found"]:
        assert set(found) == {"name", "type", "ref"}


def test_close_names_cannot_be_asked_for_without_saying_what_sort_of_thing(
    mcp_settings: Settings,
) -> None:
    import pytest as testing
    from fastmcp.exceptions import ToolError

    with testing.raises(ToolError):
        _called(mcp_settings, CLOSE_NAMES_TOOL, {"name": "dragon scimtar"})


def test_nothing_close_enough_is_an_empty_answer_rather_than_a_guess(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings,
        CLOSE_NAMES_TOOL,
        {"name": "zzzqqqwww", "type": EntityType.ITEM.value},
    )
    assert "found" not in answered
    assert answered["total"] == 0


def test_how_many_close_names_come_back_can_be_narrowed(
    mcp_settings: Settings,
) -> None:
    answered = _called(
        mcp_settings,
        CLOSE_NAMES_TOOL,
        {"name": "dragon", "type": EntityType.ITEM.value, "keep": 0.1, "limit": 1},
    )
    assert len(answered["found"]) <= 1


def test_the_same_question_asked_of_both_surfaces_is_answered_the_same_way(
    mcp_settings: Settings, client: TestClient
) -> None:
    over_mcp = _called(
        mcp_settings,
        CLOSE_NAMES_TOOL,
        {"name": "dragon", "type": EntityType.ITEM.value, "keep": 0.1},
    )
    over_http = client.get("/v1/near-names?name=dragon&type=item&keep=0.1").json()
    assert [found["ref"] for found in over_mcp["found"]] == [
        f"{result['link']['type']}:{result['link']['id']}"
        for result in over_http["items"]
    ]
    assert over_mcp["total"] == over_http["total"]


# every answer carries the build it came from


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_thing", {"name": DRAGON}),
        ("drops", {"name": DRAGON}),
        ("search", {"words": "dragon"}),
        ("list_things", {"type": "item"}),
    ],
)
def test_every_answer_says_which_build_it_came_from(
    mcp_settings: Settings, tool: str, arguments: dict[str, Any]
) -> None:
    assert _called(mcp_settings, tool, arguments)["data_version"] == "fixture-0001"


# nothing sent is bigger than what was promised


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_thing", {"name": DRAGON}),
        ("get_thing", {"name": SCIMITAR}),
        ("drops", {"name": DRAGON}),
        ("dropped_by", {"name": "Dragon bones"}),
        ("sells", {"name": "Crossbow Shop"}),
        ("search", {"words": "dragon"}),
        ("list_things", {"type": "item"}),
        ("about", {}),
    ],
)
def test_no_answer_costs_more_than_it_promised(
    mcp_settings: Settings, tool: str, arguments: dict[str, Any]
) -> None:
    answered = _called(mcp_settings, tool, arguments)
    assert len(json.dumps(answered)) < MOST_RESULT_CHARS


def test_a_thing_is_far_cheaper_than_the_page_it_came_from(
    mcp_settings: Settings, service: KnowledgeService
) -> None:
    from wiki_api.core import Found

    described = service.get_page(EntityKey(type=EntityType.NPC, id=50))
    assert isinstance(described, Found)
    answered = _called(mcp_settings, "get_thing", {"name": DRAGON})
    assert len(json.dumps(answered)) < len(described.value.model_dump_json())


def test_a_page_of_a_walk_is_the_smaller_one_a_reader_can_afford(
    mcp_settings: Settings,
) -> None:
    assert mcp_settings.mcp_rows == BLOCK_PAGE_SIZE
    assert mcp_settings.mcp_rows < mcp_settings.block_rows


# paging is followable, and totals stay honest


def test_a_page_says_exactly_what_to_pass_back(mcp_settings: Settings) -> None:
    first = _called(mcp_settings, "drops", {"name": DRAGON, "offset": 0})
    assert first["result"]["offset"] == 0
    if first["result"].get("next_offset") is not None:
        following = _called(
            mcp_settings, "drops", {"name": DRAGON, "offset": first["next_offset"]}
        )
        assert following["result"]["offset"] == first["result"]["next_offset"]


def test_paging_a_walk_to_the_end_yields_every_row_once(
    mcp_settings: Settings,
) -> None:
    seen: list[str] = []
    offset = 0
    total = None
    while True:
        answered = _called(mcp_settings, "drops", {"name": DRAGON, "offset": offset})
        reached = answered["result"]
        total = reached["total"]
        seen.extend(neighbour["name"] for neighbour in reached["neighbours"])
        if reached.get("next_offset") is None:
            break
        offset = reached["next_offset"]
    assert len(seen) == total
    assert len(set(seen)) == len(seen)


# the two surfaces answer the same question the same way


@pytest.mark.parametrize(
    ("tool", "name", "rel", "direction"),
    [
        ("drops", DRAGON, RelationshipType.DROPS, Direction.FORWARD),
        ("dropped_by", "Dragon bones", RelationshipType.DROPS, Direction.REVERSE),
        ("sells", "Crossbow Shop", RelationshipType.SELLS, Direction.FORWARD),
        ("sold_in", STOCKED, RelationshipType.SELLS, Direction.REVERSE),
        ("found_in", DRAGON, RelationshipType.LOCATED_IN, Direction.FORWARD),
    ],
)
def test_the_two_surfaces_name_the_same_things_in_the_same_order(
    mcp_settings: Settings,
    service: KnowledgeService,
    tool: str,
    name: str,
    rel: RelationshipType,
    direction: Direction,
) -> None:
    from wiki_api.core import Found

    answered = _called(mcp_settings, tool, {"name": name})
    through_core = service.walk_by_name(
        name, rel, direction, limit=mcp_settings.mcp_rows
    )
    assert isinstance(through_core.resolution, Found)
    block = through_core.resolution.value
    assert answered["result"]["total"] == block.rows.total
    assert [neighbour["name"] for neighbour in answered["result"]["neighbours"]] == [
        row.link.label for row in block.rows.items
    ]


def test_a_thing_and_a_page_agree_on_who_they_describe(
    mcp_settings: Settings, service: KnowledgeService
) -> None:
    from wiki_api.core import Found

    answered = _called(mcp_settings, "get_thing", {"name": SCIMITAR})
    described = service.get_page(EntityKey(type=EntityType.ITEM, id=4587))
    assert isinstance(described, Found)
    assert answered["result"]["ref"] == str(described.value.entity.key)


def test_the_ways_onwards_are_the_blocks_a_page_would_have_shown(
    mcp_settings: Settings, service: KnowledgeService
) -> None:
    from wiki_api.core import Found

    answered = _called(mcp_settings, "get_thing", {"name": DRAGON})
    described = service.get_page(EntityKey(type=EntityType.NPC, id=50))
    assert isinstance(described, Found)
    assert [onwards["label"] for onwards in answered["result"]["reachable"]] == [
        block.label for block in described.value.blocks
    ]


# the promise the registries make, kept here too


def test_nothing_in_this_surface_names_an_attribute_or_a_relationship() -> None:
    from pathlib import Path

    import wiki_api.surfaces.mcp as surface
    from tests.vocabulary import declared_names

    forbidden = declared_names()
    for path in Path(str(surface.__path__[0])).rglob("*.py"):
        source = path.read_text(encoding="utf-8").split("\n# test cases\n")[0]
        named = {
            word for word in forbidden if re.search(rf"\b{re.escape(word)}\b", source)
        }
        assert not named, f"{path.name} names {sorted(named)}"


def test_a_tool_is_never_named_after_a_relationship_by_hand(
    tools: dict[str, Tool],
) -> None:
    written = {name for name in tools if name in set(WRITTEN_TOOLS)}
    assert not written & {rel.value for rel in RELATIONSHIP_SPECS}


# starting up, and failing to


def test_a_server_pointed_at_no_artifact_refuses_to_start(
    tmp_path: object, mcp_settings: Settings
) -> None:
    from pathlib import Path

    from wiki_api.repository.errors import ArtifactUnavailable

    assert isinstance(tmp_path, Path)
    settings = mcp_settings.model_copy(update={"data_dir": tmp_path / "empty"})
    with pytest.raises(ArtifactUnavailable):
        create_server(settings)


def test_a_server_pointed_at_an_unreadable_artifact_refuses_to_start(
    tmp_path: object, mcp_settings: Settings
) -> None:
    from pathlib import Path

    from wiki_api.repository.errors import ArtifactUnreadable

    assert isinstance(tmp_path, Path)
    impostor = tmp_path / "knowledge.sqlite3"
    impostor.write_text("this is not a database", encoding="utf-8")
    settings = mcp_settings.model_copy(update={"data_dir": tmp_path})
    with pytest.raises(ArtifactUnreadable):
        create_server(settings)
