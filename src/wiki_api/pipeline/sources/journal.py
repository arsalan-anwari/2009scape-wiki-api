"""Read the quest journal's own list, which is where free and members quests part."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Final

from wiki_api.pipeline.staging.declared import DATAMAP_EXTRACT

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from wiki_api.pipeline.sources.staged import StagedSources

QUEST_LIST: Final = 504
CHILD_MASK: Final = 0xFFFF
TRAILING_ARTICLE: Final = re.compile(r"^(.*), (The|A|An)$")
NOT_A_LETTER: Final = re.compile(r"[^a-z0-9]+")


def folded(name: str) -> str:
    """Fold a quest name to what a comparison cares about, moving a trailing article."""
    moved = TRAILING_ARTICLE.match(name.strip())
    if moved is not None:
        name = f"{moved.group(2)} {moved.group(1)}"
    return NOT_A_LETTER.sub("", name.lower())


@dataclass(frozen=True)
class Journal:
    """The quest list as the journal draws it, folded so a name can be looked up."""

    free: frozenset[str]
    members: frozenset[str]

    @property
    def listed(self) -> frozenset[str]:
        return self.free | self.members

    def members_only(self, name: str) -> bool | None:
        """Whether the journal lists a quest under members, or nothing if absent."""
        key = folded(name)
        if key in self.free:
            return False
        if key in self.members:
            return True
        return None


def read_journal(staged: StagedSources) -> Journal:
    """Read the journal list out of the staged cache maps, or an empty one if unstaged.

    The journal draws free quests, then a heading, then members quests, so the one gap
    in the child numbering is the boundary between them.
    """
    if not staged.has_extract(DATAMAP_EXTRACT):
        return Journal(free=frozenset(), members=frozenset())
    listed = _quest_list(staged)
    if not listed:
        return Journal(free=frozenset(), members=frozenset())
    rows = sorted(listed.items())
    boundary = _boundary(tuple(child for child, _ in rows))
    return Journal(
        free=frozenset(folded(name) for child, name in rows if child <= boundary),
        members=frozenset(folded(name) for child, name in rows if child > boundary),
    )


def _quest_list(staged: StagedSources) -> dict[int, str]:
    for record in staged.stream(DATAMAP_EXTRACT):
        if record["id"] != QUEST_LIST:
            continue
        return {int(key) & CHILD_MASK: name for key, name in record["strings"].items()}
    return {}


def _boundary(children: tuple[int, ...]) -> int:
    for before, after in pairwise(children):
        if after != before + 1:
            return before
    return children[-1]


# test cases


def _staged(tmp_path: Path, maps: list[dict[str, object]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(tmp_path, {DATAMAP_EXTRACT.staged: json.dumps(maps)})


def _listed(names: Mapping[int, str]) -> list[dict[str, object]]:
    component = 274 << 16
    return [
        {
            "id": QUEST_LIST,
            "key_type": "I",
            "value_type": "s",
            "strings": {str(component | child): name for child, name in names.items()},
            "numbers": {},
        }
    ]


def test_the_gap_in_the_journal_list_parts_free_from_members(tmp_path: Path) -> None:
    journal = read_journal(
        _staged(
            tmp_path,
            _listed(
                {
                    13: "Cook's Assistant",
                    14: "Dragon Slayer",
                    16: "Desert Treasure",
                    17: "Lost City",
                }
            ),
        )
    )
    assert journal.members_only("Cook's Assistant") is False
    assert journal.members_only("Dragon Slayer") is False
    assert journal.members_only("Desert Treasure") is True
    assert journal.members_only("Lost City") is True


def test_a_quest_the_journal_never_lists_is_answered_with_nothing(
    tmp_path: Path,
) -> None:
    journal = read_journal(_staged(tmp_path, _listed({13: "Cook's Assistant"})))
    assert journal.members_only("Test Quest") is None


def test_a_name_the_journal_writes_the_other_way_round_still_matches(
    tmp_path: Path,
) -> None:
    journal = read_journal(_staged(tmp_path, _listed({13: "Knight's Sword, The"})))
    assert journal.members_only("The Knight's Sword") is False


def test_a_list_with_no_gap_is_read_as_all_free(tmp_path: Path) -> None:
    journal = read_journal(_staged(tmp_path, _listed({13: "One", 14: "Two"})))
    assert journal.members == frozenset()
    assert len(journal.listed) == 2


def test_a_cache_that_was_never_staged_answers_for_nothing(tmp_path: Path) -> None:
    from tests.sources import staged_from

    journal = read_journal(staged_from(tmp_path, {}))
    assert journal.listed == frozenset()
    assert journal.members_only("Cook's Assistant") is None


def test_a_name_folds_to_what_a_comparison_cares_about() -> None:
    assert folded("Romeo & Juliet") == folded(
        "romeo and juliet".replace(" and ", " & ")
    )
    assert folded("Restless Ghost, The") == folded("The Restless Ghost")
    assert folded("Garden of Tranquillity") != folded("Garden of Tranquility")
