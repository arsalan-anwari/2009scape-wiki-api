from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from wiki_api.core import Found, PageDescriptor
from wiki_api.domain.identity import EntityKey, EntityType

if TYPE_CHECKING:
    from wiki_api.core import KnowledgeService

SNAPSHOTS = Path(__file__).parent.parent / "fixtures" / "descriptors"

DESCRIBED = {
    "item-4587": EntityKey(type=EntityType.ITEM, id=4587),
    "npc-50": EntityKey(type=EntityType.NPC, id=50),
    "shop-53": EntityKey(type=EntityType.SHOP, id=53),
    "quest-1": EntityKey(type=EntityType.QUEST, id=1),
    "location-1": EntityKey(type=EntityType.LOCATION, id=1),
    "scenery-1276": EntityKey(type=EntityType.SCENERY, id=1276),
    "task-1": EntityKey(type=EntityType.TASK, id=1),
    "room-1": EntityKey(type=EntityType.ROOM, id=1),
}


def _descriptor(service: KnowledgeService, key: EntityKey) -> PageDescriptor:
    resolution = service.get_page(key)
    assert isinstance(resolution, Found)
    return resolution.value


def _rendered(service: KnowledgeService, key: EntityKey) -> dict[str, Any]:
    dumped: dict[str, Any] = _descriptor(service, key).model_dump(mode="json")
    return dumped


@pytest.mark.parametrize("name", sorted(DESCRIBED), ids=sorted(DESCRIBED))
def test_the_descriptor_shape_is_the_one_the_wiki_was_promised(
    service: KnowledgeService, name: str
) -> None:
    snapshot = SNAPSHOTS / f"{name}.json"
    expected = json.loads(snapshot.read_text(encoding="utf-8"))
    assert _rendered(service, DESCRIBED[name]) == expected


def test_both_repositories_describe_a_page_identically(
    service: KnowledgeService,
) -> None:
    for key in DESCRIBED.values():
        rendered = _rendered(service, key)
        assert rendered["entity"]["slug"]
        assert rendered["data_version"] == "fixture-0001"


def test_a_descriptor_serialises_to_json_and_back(service: KnowledgeService) -> None:
    for key in DESCRIBED.values():
        descriptor = _descriptor(service, key)
        restored = PageDescriptor.model_validate_json(descriptor.model_dump_json())
        assert restored == descriptor


def test_a_descriptor_carries_no_url_anywhere_in_it(
    service: KnowledgeService,
) -> None:
    for key in DESCRIBED.values():
        rendered = json.dumps(_rendered(service, key))
        assert "http" not in rendered
        assert "/wiki/" not in rendered
