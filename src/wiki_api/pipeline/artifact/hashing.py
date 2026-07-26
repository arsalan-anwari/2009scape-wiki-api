"""Hashing a snapshot so two builds of the same sources can be compared."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot


def content_hash(snapshot: KnowledgeSnapshot) -> str:
    """A hash of the snapshot content that ignores when the build ran."""
    payload = snapshot.model_dump(mode="json")
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# test cases


def test_the_same_content_always_hashes_the_same() -> None:
    from wiki_api.pipeline.artifact.merge import merge
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    payload = {
        "schema": 1,
        "source": "fixture",
        "game_version": "test",
        "entities": [{"type": "item", "id": 4587, "name": "Dragon scimitar"}],
    }
    first = merge(
        [OverlaySource.model_validate({"origin": "a.json", "document": payload})]
    )
    second = merge(
        [OverlaySource.model_validate({"origin": "a.json", "document": payload})]
    )
    assert content_hash(first) == content_hash(second)
    assert len(content_hash(first)) == 64


def test_changed_content_changes_the_hash() -> None:
    from wiki_api.pipeline.artifact.merge import merge
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    def snapshot_for(name: str) -> object:
        payload = {
            "schema": 1,
            "source": "fixture",
            "game_version": "test",
            "entities": [{"type": "item", "id": 4587, "name": name}],
        }
        return merge(
            [OverlaySource.model_validate({"origin": "a.json", "document": payload})]
        )

    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

    first = snapshot_for("Dragon scimitar")
    second = snapshot_for("Dragon scimmy")
    assert isinstance(first, KnowledgeSnapshot)
    assert isinstance(second, KnowledgeSnapshot)
    assert content_hash(first) != content_hash(second)
