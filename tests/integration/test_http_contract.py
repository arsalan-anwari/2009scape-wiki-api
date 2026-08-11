from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from wiki_api.domain.page import MAX_PAGE_SIZE
from wiki_api.surfaces.http import create_app
from wiki_api.surfaces.http.caching import DATA_VERSION_HEADER

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from wiki_api.config import Settings

SCIMITAR = "/v1/entities/item/4587"
NOTED_SCIMITAR = "/v1/entities/item/4588"
KBD = "/v1/entities/npc/50"
CROSSBOW_SHOP = "/v1/entities/shop/53"
DEATH_PLATEAU = "/v1/entities/quest/1"
KBD_LAIR = "/v1/entities/location/1"
UNNAMED_NPC = "/v1/entities/npc/3089"
RETIRED = "/v1/entities/item/dragon-scimmy"
NOWHERE = "/v1/entities/item/999999"

SNAPSHOTS = Path(__file__).parent.parent / "fixtures" / "descriptors"


def _body(client: TestClient, url: str) -> dict[str, Any]:
    response = client.get(url)
    assert response.status_code == 200, response.text
    answered: dict[str, Any] = response.json()
    return answered


def _links(client: TestClient, url: str) -> list[str]:
    return [row["link"]["label"] for row in _body(client, url)["rows"]["items"]]


def _labels(client: TestClient, url: str) -> list[str]:
    return [item["link"]["label"] for item in _body(client, url)["items"]]


def _shown(descriptor: dict[str, Any]) -> dict[str, Any]:
    values = list(descriptor["infobox"])
    for section in descriptor["sections"]:
        values.extend(section["attributes"])
    return {value["key"]: value for value in values}


# the questions this phase has to answer, one call each


def test_what_are_the_details_of_an_item(client: TestClient) -> None:
    descriptor = _body(client, SCIMITAR)
    assert descriptor["entity"]["label"] == "Dragon scimitar"
    assert descriptor["description"] == "A vicious, curved sword."
    assert "tradeable" in _shown(descriptor)


def test_what_are_the_stats_of_an_npc(client: TestClient) -> None:
    shown = _shown(_body(client, KBD))
    assert shown["lifepoints"]["value"] == 240
    assert shown["lifepoints"]["label"] == "Lifepoints"


def test_which_items_does_a_shop_sell(client: TestClient) -> None:
    sold = _links(client, f"{CROSSBOW_SHOP}/rel/sells?direction=forward")
    assert "Wooden stock" in sold


def test_which_shops_sell_an_item(client: TestClient) -> None:
    sellers = _links(client, "/v1/entities/item/9440/rel/sells?direction=reverse")
    assert sellers == ["Crossbow Shop (White Wolf Mountain)"]


def test_which_items_does_an_npc_drop(client: TestClient) -> None:
    dropped = _links(client, f"{KBD}/rel/drops?direction=forward")
    assert "Dragon bones" in dropped


def test_which_npcs_drop_an_item(client: TestClient) -> None:
    droppers = _links(client, "/v1/entities/item/536/rel/drops?direction=reverse")
    assert droppers == ["King Black Dragon"]


def test_a_reverse_walk_over_http_covers_the_variants_too(client: TestClient) -> None:
    droppers = _links(client, f"{SCIMITAR}/rel/drops?direction=reverse")
    assert droppers == ["King Black Dragon"]


def test_where_is_an_npc_on_the_map(client: TestClient) -> None:
    placed = _links(client, f"{KBD}/rel/located_in?direction=forward")
    assert placed == ["King Black Dragon Lair"]


def test_where_is_a_shop_on_the_map(client: TestClient) -> None:
    placed = _links(client, f"{CROSSBOW_SHOP}/rel/located_in?direction=forward")
    assert placed


def test_what_is_found_at_a_location(client: TestClient) -> None:
    present = _links(client, f"{KBD_LAIR}/rel/located_in?direction=reverse")
    assert "King Black Dragon" in present


def test_where_is_a_place_on_the_map(client: TestClient) -> None:
    shown = _shown(_body(client, KBD_LAIR))
    assert "centre" in shown
    assert shown["centre"]["format"] == "coord"


def test_which_quests_are_available(client: TestClient) -> None:
    assert "Death Plateau" in _labels(client, "/v1/types/quest/entities")


def test_which_npcs_are_available(client: TestClient) -> None:
    assert "King Black Dragon" in _labels(client, "/v1/types/npc/entities")


def test_which_items_are_available(client: TestClient) -> None:
    assert "Dragon scimitar" in _labels(client, "/v1/types/item/entities")


def test_what_is_this_in_one_hover(client: TestClient) -> None:
    hover = _body(client, f"{KBD}/tooltip")
    assert hover["link"]["label"] == "King Black Dragon"
    assert {value["key"] for value in hover["attributes"]} == {
        "aggressive",
        "lifepoints",
    }
    assert all(value["prominent"] for value in hover["attributes"])
    assert "blocks" not in hover


def test_what_can_i_search_for(client: TestClient) -> None:
    found = _body(client, "/v1/search?q=dragon")
    assert found["total"] >= 1
    assert all(result["score"] >= 0 for result in found["items"])


def test_the_thing_called_this(client: TestClient) -> None:
    matched = _body(client, "/v1/find?name=Dragon scimitar")
    assert matched["best_match"]["id"] == 4587


def test_what_did_i_mean_by_this_misspelling(client: TestClient) -> None:
    offered = _body(client, "/v1/near-names?name=dragon scimtar&type=item")
    assert [result["link"]["id"] for result in offered["items"]] == [4587]


def test_a_near_name_answer_carries_no_more_than_identity(client: TestClient) -> None:
    offered = _body(client, "/v1/near-names?name=dragon scimtar&type=item")
    assert offered["items"]
    for result in offered["items"]:
        assert result["description"] is None
        assert set(result) == {"link", "type", "score", "description"}


def test_a_near_name_answer_is_empty_when_nothing_is_close(client: TestClient) -> None:
    offered = _body(client, "/v1/near-names?name=zzzqqqwww&type=item")
    assert offered["items"] == []
    assert offered["total"] == 0


def test_a_near_name_question_without_a_sort_of_thing_is_refused(
    client: TestClient,
) -> None:
    assert client.get("/v1/near-names?name=dragon scimtar").status_code == 422


def test_a_near_name_answer_can_be_asked_to_be_narrower(client: TestClient) -> None:
    wide = _body(client, "/v1/near-names?name=dragon&type=item&keep=0.1")
    narrow = _body(client, "/v1/near-names?name=dragon&type=item&keep=0.1&limit=1")
    assert len(narrow["items"]) <= 1 <= len(wide["items"])


def test_a_near_name_answer_can_never_be_asked_to_be_a_listing(
    client: TestClient,
) -> None:
    asked = "/v1/near-names?name=dragon&type=item&limit=99"
    assert client.get(asked).status_code == 422


def test_a_name_nobody_answers_to_says_where_to_ask_what_it_meant(
    client: TestClient,
) -> None:
    response = client.get("/v1/entities/item/dragon-scimtar")
    assert response.status_code == 404
    reported = response.json()["error"]
    assert reported["code"] == "not_found"
    assert reported["near_names"] == "/v1/near-names?name=dragon+scimtar&type=item"


def test_an_id_nobody_answers_to_offers_no_spelling_help(client: TestClient) -> None:
    response = client.get("/v1/entities/item/999999")
    assert response.status_code == 404
    assert "near_names" not in response.json()["error"]


def test_what_types_exist_and_how_do_their_fields_present(client: TestClient) -> None:
    response = client.get("/v1/types")
    assert response.status_code == 200
    published = response.json()
    assert {info["type"] for info in published} == {
        "item",
        "npc",
        "shop",
        "quest",
        "location",
        "scenery",
        "task",
        "room",
    }
    assert all(info["attributes"] for info in published)


def test_which_artifact_am_i_reading(client: TestClient) -> None:
    about = _body(client, "/v1/about")
    assert about["data_version"] == "fixture-0001"
    assert about["schema_version"] >= 1


# how a thing is addressed


def test_an_entity_is_reachable_by_id_and_by_slug(client: TestClient) -> None:
    by_id = _body(client, SCIMITAR)
    by_slug = _body(client, "/v1/entities/item/dragon-scimitar")
    assert by_id == by_slug


def test_a_hand_authored_entity_is_reachable_by_the_token_its_source_used(
    client: TestClient,
) -> None:
    by_id = _body(client, DEATH_PLATEAU)
    by_source = _body(client, "/v1/entities/quest/DEATH_PLATEAU")
    assert by_id == by_source


def test_a_run_of_digits_is_read_as_an_identity(client: TestClient) -> None:
    assert _body(client, SCIMITAR)["entity"]["id"] == 4587


# absence, in all four of its shapes


def test_a_retired_slug_sends_a_reader_to_where_the_thing_lives_now(
    client: TestClient,
) -> None:
    response = client.get(RETIRED, follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == SCIMITAR


def test_a_redirect_keeps_the_resource_that_was_asked_for(client: TestClient) -> None:
    response = client.get(f"{RETIRED}/tooltip", follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == f"{SCIMITAR}/tooltip"


def test_a_redirect_keeps_the_question_that_was_asked(client: TestClient) -> None:
    asked = f"{RETIRED}/rel/drops?direction=reverse&limit=5"
    response = client.get(asked, follow_redirects=False)
    assert response.status_code == 308
    assert response.headers["location"] == (
        f"{SCIMITAR}/rel/drops?direction=reverse&limit=5"
    )


def test_following_a_redirect_lands_on_the_thing_itself(client: TestClient) -> None:
    assert _body(client, RETIRED)["entity"]["id"] == 4587


def test_an_unpublished_entity_is_absent_but_says_which_way(
    client: TestClient,
) -> None:
    response = client.get(UNNAMED_NPC)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_published"


def test_an_entity_that_was_never_there_is_plainly_absent(client: TestClient) -> None:
    response = client.get(NOWHERE)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_absence_reads_the_same_on_every_resource_of_a_thing(
    client: TestClient,
) -> None:
    for suffix in ("", "/tooltip", "/rel/drops"):
        response = client.get(f"{NOWHERE}{suffix}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_a_reader_can_ask_what_a_reference_names_without_being_sent_there(
    client: TestClient,
) -> None:
    inspected = _body(client, f"{RETIRED}/resolve")
    assert inspected["outcome"] == "moved"
    assert inspected["target"]["id"] == 4587


def test_inspecting_a_live_reference_says_it_is_live(client: TestClient) -> None:
    inspected = _body(client, f"{SCIMITAR}/resolve")
    assert inspected["outcome"] == "found"
    assert inspected["target"]["slug"] == "dragon-scimitar"


def test_inspecting_an_unpublished_reference_says_so_rather_than_refusing(
    client: TestClient,
) -> None:
    inspected = _body(client, f"{UNNAMED_NPC}/resolve")
    assert inspected["outcome"] == "hidden"


def test_inspecting_nothing_at_all_says_so(client: TestClient) -> None:
    assert _body(client, f"{NOWHERE}/resolve")["outcome"] == "missing"


def test_nothing_a_reader_is_refused_leaks_an_internal_detail(
    client: TestClient,
) -> None:
    reported = client.get(UNNAMED_NPC).text
    assert "sqlite" not in reported.lower()
    assert "Traceback" not in reported


# variants render rather than redirect


def test_a_noted_variant_renders_a_page_of_its_own(client: TestClient) -> None:
    descriptor = _body(client, NOTED_SCIMITAR)
    assert descriptor["entity"]["id"] == 4588
    assert descriptor["canonical"]["id"] == 4587


def test_the_page_of_a_variant_shows_what_the_real_thing_relates_to(
    client: TestClient,
) -> None:
    droppers = _links(client, f"{NOTED_SCIMITAR}/rel/drops?direction=reverse")
    assert droppers == ["King Black Dragon"]


def test_a_canonical_page_owns_up_to_its_variants(client: TestClient) -> None:
    assert [link["id"] for link in _body(client, SCIMITAR)["variants"]] == [4588]


# the descriptor is handed over exactly as the core built it


@pytest.mark.parametrize(
    "name",
    [
        "item-4587",
        "npc-50",
        "shop-53",
        "quest-1",
        "location-1",
        "scenery-1276",
        "task-1",
        "room-1",
    ],
)
def test_the_page_served_is_the_page_the_core_described(
    preview_client: TestClient, name: str
) -> None:
    entity_type, entity_id = name.rsplit("-", 1)
    served = _body(preview_client, f"/v1/entities/{entity_type}/{entity_id}")
    expected = json.loads((SNAPSHOTS / f"{name}.json").read_text(encoding="utf-8"))
    assert served == expected


def test_a_page_carries_no_url_anywhere_in_it(client: TestClient) -> None:
    rendered = client.get(SCIMITAR).text
    assert "http://" not in rendered
    assert "https://" not in rendered


def test_a_section_says_how_it_wants_to_be_laid_out(client: TestClient) -> None:
    sections = _body(client, SCIMITAR)["sections"]
    assert all(section["render"] for section in sections)


# a block and a walk are the same page


def test_the_first_page_of_a_block_is_what_the_walk_returns(
    client: TestClient,
) -> None:
    descriptor = _body(client, KBD)
    for block in descriptor["blocks"]:
        walk = block["walk"]
        served = _body(
            client,
            f"/v1/entities/{walk['origin']['type']}/{walk['origin']['id']}"
            f"/rel/{walk['rel']}?direction={walk['direction']}&limit={block['rows']['limit']}",
        )
        assert served["rows"]["items"] == block["rows"]["items"]
        assert served["label"] == block["label"]


def test_a_page_of_a_walk_tells_a_reader_where_the_next_one_starts(
    client: TestClient,
) -> None:
    served = _body(client, f"{KBD}/rel/drops?direction=forward&limit=1")
    rows = served["rows"]
    assert rows["has_more"] is (rows["total"] > 1)
    assert rows["next_offset"] == (1 if rows["has_more"] else None)


def test_paging_a_walk_yields_every_row_once(client: TestClient) -> None:
    seen: list[int] = []
    offset = 0
    while True:
        rows = _body(client, f"{KBD}/rel/drops?limit=1&offset={offset}")["rows"]
        seen.extend(row["link"]["id"] for row in rows["items"])
        if rows["next_offset"] is None:
            break
        offset = rows["next_offset"]
    assert len(seen) == len(set(seen))
    assert len(seen) == rows["total"]


def test_a_page_carries_enough_rows_to_be_worth_reading(
    client: TestClient, http_settings: Settings
) -> None:
    for block in _body(client, KBD)["blocks"]:
        assert block["rows"]["limit"] == http_settings.block_rows
    assert http_settings.block_rows == 60


def test_how_many_rows_a_page_carries_is_the_deployment_s_call(
    preview_client: TestClient,
) -> None:
    for block in _body(preview_client, KBD)["blocks"]:
        assert block["rows"]["limit"] == 10


def test_showing_the_rest_is_no_narrower_than_what_the_page_showed(
    client: TestClient, http_settings: Settings
) -> None:
    block = _body(client, KBD)["blocks"][0]
    walk = block["walk"]
    served = _body(client, f"{KBD}/rel/{walk['rel']}?direction={walk['direction']}")
    assert served["rows"]["limit"] == block["rows"]["limit"]
    assert served["rows"]["limit"] == http_settings.block_rows


def test_a_continuation_follows_the_page_it_continues(
    preview_client: TestClient,
) -> None:
    served = _body(preview_client, f"{KBD}/rel/drops?direction=forward")
    assert served["rows"]["limit"] == 10


def test_a_caller_who_says_how_many_rows_it_wants_still_gets_them(
    client: TestClient,
) -> None:
    served = _body(client, f"{KBD}/rel/drops?direction=forward&limit=1")
    assert served["rows"]["limit"] == 1


def test_a_listing_tells_a_reader_where_the_next_page_starts(
    client: TestClient,
) -> None:
    listed = _body(client, "/v1/types/item/entities?limit=1")
    assert listed["has_more"] is True
    assert listed["next_offset"] == 1


# what a thing has been worth, and how far to believe it


def test_what_an_item_has_been_worth_is_read_a_page_at_a_time(
    client: TestClient,
) -> None:
    read = _body(client, "/v1/entities/item/4587/prices")
    assert read["total"] == 4
    assert [point["value"] for point in read["items"]] == [
        106049,
        106049,
        108601,
        108590,
    ]


def test_a_reading_can_start_from_a_day(client: TestClient) -> None:
    read = _body(client, "/v1/entities/item/4587/prices?since=2026-01-01")
    assert [point["value"] for point in read["items"]] == [108601, 108590]


def test_a_reading_pages_like_every_other_listing(client: TestClient) -> None:
    read = _body(client, "/v1/entities/item/4587/prices?limit=2")
    assert len(read["items"]) == 2
    assert read["next_offset"] == 2


def test_a_thing_the_market_never_recorded_answers_empty_rather_than_absent(
    client: TestClient,
) -> None:
    read = _body(client, "/v1/entities/npc/50/prices")
    assert read["items"] == []
    assert read["total"] == 0


def test_a_reading_asked_of_nothing_is_still_a_not_found(client: TestClient) -> None:
    assert client.get("/v1/entities/item/999999/prices").status_code == 404


def test_an_item_page_says_what_it_is_worth_and_how_far_to_trust_it(
    client: TestClient,
) -> None:
    page = _body(client, "/v1/entities/item/4587")
    values = {
        value["key"]: value
        for section in page["sections"]
        for value in section["attributes"]
    }
    assert values["market_price"]["value"] == 108590
    assert values["market_confidence"]["value"] == "traded"
    assert values["market_price"]["derived"] is True


# a question whose subject is a number rather than a name


def _compared(client: TestClient, asked: str) -> dict[str, Any]:
    return _body(client, f"/v1/types/item/compare?{asked}")


def test_a_listing_can_be_narrowed_by_a_number_it_stores(client: TestClient) -> None:
    read = _compared(client, "holds=ge_buy_limit&how=at_least&number=10000")
    assert read["rows"]["total"] == 3
    assert {row["link"]["label"] for row in read["rows"]["items"]} == {
        "Bronze bolts",
        "Dragon bones",
        "Logs",
    }


def test_one_part_of_a_packed_value_is_compared_on_its_own(
    client: TestClient,
) -> None:
    read = _compared(client, "holds=bonuses.strength&how=more_than&number=10")
    assert [row["link"]["label"] for row in read["rows"]["items"]] == [
        "Dragon scimitar"
    ]


def test_a_value_may_be_named_by_the_label_the_registry_publishes(
    client: TestClient,
) -> None:
    by_key = _compared(client, "holds=bonuses.strength&how=more_than&number=10")
    by_label = _compared(client, "holds=Strength%20bonus&how=more_than&number=10")
    assert by_key == by_label


def test_a_comparison_answers_with_the_values_it_was_made_on(
    client: TestClient,
) -> None:
    read = _compared(client, "holds=bonuses.strength&how=more_than&number=10")
    shown = read["rows"]["items"][0]["attributes"]
    assert [value["key"] for value in shown] == ["bonuses.strength"]
    assert shown[0]["label"] == "Strength bonus"
    assert shown[0]["value"] == 66
    assert isinstance(shown[0]["value"], int)


def test_a_compared_value_keeps_the_shape_the_record_stores_it_in(
    client: TestClient,
) -> None:
    read = _compared(client, "holds=weight&how=at_least&number=10")
    shown = read["rows"]["items"][0]["attributes"][0]
    assert shown["value"] == 10.0
    assert isinstance(shown["value"], float)


def test_a_listing_can_be_ordered_by_a_number_it_stores(client: TestClient) -> None:
    read = _compared(client, "ordered_by=weight&descending=true&limit=3")
    assert [row["link"]["label"] for row in read["rows"]["items"]] == [
        "Kbd heads",
        "Phoenix crossbow",
        "Logs",
    ]


def test_the_question_comes_back_beside_the_answer(client: TestClient) -> None:
    read = _compared(client, "holds=weight&how=at_most&number=1&ordered_by=weight")
    assert read["where"] == [{"path": "weight", "compare": "at_most", "value": 1.0}]
    assert read["order"] == {"path": "weight", "descending": False}
    assert read["type"] == "item"


def test_a_comparison_pages_like_every_other_listing(client: TestClient) -> None:
    read = _compared(client, "ordered_by=weight&limit=2")
    assert len(read["rows"]["items"]) == 2
    assert read["rows"]["next_offset"] == 2


def test_words_no_declared_value_answers_to_are_refused(client: TestClient) -> None:
    answered = client.get("/v1/types/item/compare?holds=how%20shiny%20it%20is")
    assert answered.status_code == 422
    assert answered.json()["error"]["code"] == "invalid_request"


def test_naming_nothing_to_compare_is_refused_rather_than_listed(
    client: TestClient,
) -> None:
    assert client.get("/v1/types/item/compare").status_code == 422


def test_a_value_belonging_to_another_type_is_refused(client: TestClient) -> None:
    answered = client.get("/v1/types/quest/compare?holds=bonuses.strength")
    assert answered.status_code == 422


# caching, because a build never changes underneath a reader


def test_every_answer_says_which_build_it_came_from(client: TestClient) -> None:
    for url in (SCIMITAR, f"{KBD}/tooltip", "/v1/search?q=dragon", "/v1/types"):
        assert client.get(url).headers[DATA_VERSION_HEADER] == "fixture-0001"


def test_an_answer_can_be_validated_rather_than_sent_again(
    client: TestClient,
) -> None:
    first = client.get(SCIMITAR)
    again = client.get(SCIMITAR, headers={"if-none-match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""


def test_a_validator_from_one_question_does_not_answer_another(
    client: TestClient,
) -> None:
    page = client.get(SCIMITAR)
    hover = client.get(
        f"{SCIMITAR}/tooltip", headers={"if-none-match": page.headers["etag"]}
    )
    assert hover.status_code == 200


def test_a_hover_is_held_longer_than_a_page(client: TestClient) -> None:
    page = client.get(SCIMITAR).headers["cache-control"]
    hover = client.get(f"{SCIMITAR}/tooltip").headers["cache-control"]
    assert page != hover
    assert "max-age=3600" in hover


def test_pinning_to_the_build_being_served_makes_an_answer_keep_forever(
    client: TestClient,
) -> None:
    response = client.get(f"{SCIMITAR}?v=fixture-0001")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]


def test_pinning_to_a_build_that_is_gone_is_refused_rather_than_answered(
    client: TestClient,
) -> None:
    response = client.get(f"{SCIMITAR}?v=fixture-0000")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "data_version_mismatch"


def test_a_refused_pin_says_which_build_is_here_instead(
    client: TestClient,
) -> None:
    response = client.get(f"{SCIMITAR}?v=fixture-0000")
    assert response.json()["error"]["data_version"] == "fixture-0001"
    assert response.headers[DATA_VERSION_HEADER] == "fixture-0001"


def test_recovering_from_a_refused_pin_costs_one_retry_and_no_more(
    client: TestClient,
) -> None:
    refused = client.get(f"{SCIMITAR}?v=fixture-0000")
    current = refused.json()["error"]["data_version"]
    retried = client.get(f"{SCIMITAR}?v={current}")
    assert retried.status_code == 200
    assert "immutable" in retried.headers["cache-control"]


def test_a_failure_a_caller_cannot_act_on_says_nothing_extra(
    client: TestClient,
) -> None:
    reported = client.get(NOWHERE).json()["error"]
    assert set(reported) == {"code", "message"}


def test_what_this_process_is_is_never_cached(client: TestClient) -> None:
    for url in ("/health", "/v1/about"):
        assert client.get(url).headers["cache-control"] == "no-store"


def test_a_process_with_an_artifact_open_is_healthy(client: TestClient) -> None:
    health = _body(client, "/health")
    assert health["status"] == "ok"
    assert health["data_version"] == "fixture-0001"


# what a caller is not allowed to ask


def test_a_page_larger_than_the_contract_allows_is_refused_not_broken(
    client: TestClient,
) -> None:
    response = client.get(f"/v1/types/item/entities?limit={MAX_PAGE_SIZE + 1}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_a_page_that_starts_before_the_beginning_is_refused(
    client: TestClient,
) -> None:
    assert client.get("/v1/types/item/entities?offset=-1").status_code == 422


def test_a_type_that_does_not_exist_is_refused(client: TestClient) -> None:
    response = client.get("/v1/entities/spell/1")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_a_relationship_that_does_not_exist_is_refused(client: TestClient) -> None:
    assert client.get(f"{SCIMITAR}/rel/befriends").status_code == 422


def test_a_search_with_no_words_is_refused(client: TestClient) -> None:
    assert client.get("/v1/search").status_code == 422


def test_a_route_nobody_serves_answers_in_the_same_envelope(
    client: TestClient,
) -> None:
    response = client.get("/v1/nothing-here")
    assert response.status_code == 404
    assert set(response.json()) == {"error"}


def test_nothing_may_be_written_through_this_contract(client: TestClient) -> None:
    assert client.post(SCIMITAR).status_code in {404, 405}


# a browser on another origin can use this


def test_a_front_end_elsewhere_is_allowed_in(client: TestClient) -> None:
    origin = "https://wiki.example.test"
    response = client.get(SCIMITAR, headers={"origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_a_front_end_can_read_the_headers_it_caches_with(client: TestClient) -> None:
    response = client.get(SCIMITAR, headers={"origin": "https://wiki.example.test"})
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "etag" in exposed
    assert DATA_VERSION_HEADER in exposed


# the promise the registries make, kept at the surface too


def test_nothing_in_the_surface_names_an_attribute_or_a_relationship() -> None:
    import wiki_api.surfaces as surfaces
    from tests.vocabulary import declared_names

    forbidden = declared_names()
    for path in Path(str(surfaces.__path__[0])).rglob("*.py"):
        source = path.read_text(encoding="utf-8").split("\n# test cases\n")[0]
        named = {
            word for word in forbidden if re.search(rf"\b{re.escape(word)}\b", source)
        }
        assert not named, f"{path.name} names {sorted(named)}"


# starting up, and failing to


def test_a_process_pointed_at_no_artifact_refuses_to_start(
    tmp_path: Path, http_settings: Settings
) -> None:
    from fastapi.testclient import TestClient as Client

    from wiki_api.repository.errors import ArtifactUnavailable

    settings = http_settings.model_copy(update={"data_dir": tmp_path / "empty"})
    with pytest.raises(ArtifactUnavailable), Client(create_app(settings)):
        pass


def test_a_process_pointed_at_an_unreadable_artifact_refuses_to_start(
    tmp_path: Path, http_settings: Settings
) -> None:
    from fastapi.testclient import TestClient as Client

    from wiki_api.repository.errors import ArtifactUnreadable

    impostor = tmp_path / "knowledge.sqlite3"
    impostor.write_text("this is not a database", encoding="utf-8")
    settings = http_settings.model_copy(update={"data_dir": tmp_path})
    with pytest.raises(ArtifactUnreadable), Client(create_app(settings)):
        pass


def test_a_type_the_contract_never_knew_serves_a_page_like_any_other(
    client: TestClient,
) -> None:
    page = _body(client, "/v1/entities/scenery/tree")
    assert page["entity"]["label"] == "Tree"
    assert page["infobox"]
    assert [block["label"] for block in page["blocks"]] == ["Yields"]


def test_a_walk_from_a_type_the_contract_never_knew_is_paged(
    client: TestClient,
) -> None:
    walked = _body(client, "/v1/entities/scenery/1276/rel/yields?direction=forward")
    assert [row["link"]["label"] for row in walked["rows"]["items"]] == ["Logs"]
