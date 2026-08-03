"""Hash a snapshot so two builds of the same sources can be compared."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

RECORD_SEPARATOR: Final = b"\x1e"


def content_hash(snapshot: KnowledgeSnapshot) -> str:
    """A hash of the snapshot content that ignores when the build ran.

    Rows are folded in one at a time, so a build holding millions of them never
    serialises the whole snapshot into one string.
    """
    digest = hashlib.sha256()
    for line in _lines(snapshot):
        digest.update(line)
        digest.update(RECORD_SEPARATOR)
    return digest.hexdigest()


def _lines(snapshot: KnowledgeSnapshot) -> Iterator[bytes]:
    for name, rows in (
        ("entities", snapshot.entities),
        ("edges", snapshot.edges),
        ("aliases", snapshot.aliases),
        ("prices", snapshot.prices),
    ):
        yield name.encode("utf-8")
        yield from _rows(rows)


def _rows(rows: Iterable[Any]) -> Iterator[bytes]:
    for row in rows:
        yield json.dumps(
            row.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")


# test cases


def _snapshot(name: str = "Dragon scimitar") -> KnowledgeSnapshot:
    from wiki_api.pipeline.artifact.merge import merge
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    payload = {
        "schema": 1,
        "source": "fixture",
        "game_version": "test",
        "entities": [{"type": "item", "id": 4587, "name": name}],
    }
    return merge(
        [OverlaySource.model_validate({"origin": "a.json", "document": payload})]
    )


def test_the_same_content_always_hashes_the_same() -> None:
    assert content_hash(_snapshot()) == content_hash(_snapshot())
    assert len(content_hash(_snapshot())) == 64


def test_changed_content_changes_the_hash() -> None:
    assert content_hash(_snapshot()) != content_hash(_snapshot("Dragon scimmy"))


def test_an_empty_snapshot_still_hashes() -> None:
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

    assert len(content_hash(KnowledgeSnapshot())) == 64


def test_a_row_moving_between_two_kinds_of_row_changes_the_hash() -> None:
    from wiki_api.domain.alias import AliasKind, EntityAlias
    from wiki_api.domain.identity import EntityType
    from wiki_api.pipeline.artifact.snapshot import KnowledgeSnapshot

    alias = EntityAlias(
        type=EntityType.ITEM,
        slug="dscim",
        entity_id=4587,
        kind=AliasKind.SHORTHAND,
    )
    with_alias = KnowledgeSnapshot(aliases=(alias,))
    assert content_hash(with_alias) != content_hash(KnowledgeSnapshot())
