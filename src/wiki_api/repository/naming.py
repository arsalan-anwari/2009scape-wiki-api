"""Work out which real names a misspelt one might have meant, over the names alone."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Final

from wiki_api.domain.search import NEAR_FLOOR, NEAR_KEEP, NEAR_LIMIT

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wiki_api.domain.identity import EntityKey

RUN_LENGTH: Final = 3
CANDIDATE_WIDTH: Final = 60


@dataclass(frozen=True)
class Nearby:
    """One candidate name, with how close it came."""

    key: EntityKey
    score: float


def fold(text: str) -> str:
    """Fold a name to what a comparison cares about."""
    stripped = unicodedata.normalize("NFKD", text).encode("ascii", "ignore")
    return " ".join(stripped.decode("ascii").lower().split())


def runs(folded: str) -> frozenset[str]:
    """Cut a name into three-letter runs, padded so its start counts too."""
    padded = f"  {folded} "
    return frozenset(
        padded[at : at + RUN_LENGTH] for at in range(len(padded) - RUN_LENGTH + 1)
    )


class NameIndex:
    """Index one sort of thing's names, so a near miss is cheap to answer."""

    def __init__(self, rows: Iterable[tuple[EntityKey, str]]) -> None:
        self._keys: list[EntityKey] = []
        self._names: list[str] = []
        self._sizes: list[int] = []
        self._postings: dict[str, list[int]] = {}
        self._at: dict[str, int] = {}
        for key, name in rows:
            self._add(key, name)

    def __len__(self) -> int:
        return len(self._names)

    def near(
        self,
        query: str,
        *,
        limit: int = NEAR_LIMIT,
        keep: float = NEAR_KEEP,
        floor: float = NEAR_FLOOR,
        width: int = CANDIDATE_WIDTH,
    ) -> tuple[Nearby, ...]:
        """Return the closest names to `query`, or nothing when the best falls under
        `floor`.
        """
        asked = fold(query)
        if not asked or limit < 1:
            return ()
        wanted = runs(asked)
        shared = self._shared(wanted)
        if not shared:
            return ()
        narrowed = sorted(
            (
                (2 * count / (len(wanted) + self._sizes[at]), at)
                for at, count in shared.items()
            ),
            key=lambda scored: (-scored[0], self._ordering(scored[1])),
        )[:width]
        scored = sorted(
            (
                (SequenceMatcher(None, asked, self._names[at]).ratio(), at)
                for _, at in narrowed
            ),
            key=lambda scored: (-scored[0], self._ordering(scored[1])),
        )
        best = scored[0][0]
        if best < floor:
            return ()
        threshold = keep * best
        return tuple(
            Nearby(key=self._keys[at], score=score)
            for score, at in scored
            if score >= threshold
        )[:limit]

    def _add(self, key: EntityKey, name: str) -> None:
        folded = fold(name)
        if not folded:
            return
        seen = self._at.get(folded)
        if seen is not None:
            if _before(key, self._keys[seen]):
                self._keys[seen] = key
            return
        at = len(self._names)
        self._at[folded] = at
        self._names.append(folded)
        self._keys.append(key)
        held = runs(folded)
        self._sizes.append(len(held))
        for run in held:
            self._postings.setdefault(run, []).append(at)

    def _shared(self, wanted: frozenset[str]) -> dict[int, int]:
        shared: dict[int, int] = {}
        for run in wanted:
            for at in self._postings.get(run, ()):
                shared[at] = shared.get(at, 0) + 1
        return shared

    def _ordering(self, at: int) -> tuple[str, int]:
        key = self._keys[at]
        return key.type.value, key.id


def _before(key: EntityKey, other: EntityKey) -> bool:
    return (key.type.value, key.id) < (other.type.value, other.id)


# test cases


def _key(id: int) -> EntityKey:
    from wiki_api.domain.identity import EntityKey as Identity
    from wiki_api.domain.identity import EntityType

    return Identity(type=EntityType.ITEM, id=id)


def _index() -> NameIndex:
    return NameIndex(
        (
            (_key(4587), "Dragon scimitar"),
            (_key(1305), "Dragon longsword"),
            (_key(3105), "Climbing boots"),
            (_key(995), "Coins"),
            (_key(536), "Dragon bones"),
        )
    )


def test_a_name_is_reduced_to_what_a_comparison_cares_about() -> None:
    assert fold("  Dragon   SCIMITAR ") == "dragon scimitar"
    assert fold("Café") == "cafe"
    assert fold("   ") == ""


def test_a_short_name_still_has_runs_to_match_on() -> None:
    assert "  c" in runs("coins")
    assert len(runs("coins")) == len({"  c", " co", "coi", "oin", "ins", "ns "})


def test_a_letter_left_out_still_finds_the_name_that_was_meant() -> None:
    found = _index().near("dragon scimtar")
    assert [nearby.key.id for nearby in found] == [4587]


def test_a_letter_typed_twice_still_finds_the_name_that_was_meant() -> None:
    assert _index().near("climbingg boots")[0].key.id == 3105


def test_nothing_close_is_answered_with_nothing_rather_than_the_least_bad() -> None:
    assert _index().near("qqqqqqqqqqqq") == ()


def test_a_few_letters_of_a_name_are_not_a_misspelling_of_it() -> None:
    assert _index().near("drag") == ()


def test_a_lower_floor_will_accept_what_the_usual_one_refuses() -> None:
    assert _index().near("drag", floor=0.4)


def test_letting_more_through_offers_more_of_the_same_family() -> None:
    tight = _index().near("dragon scimtar", keep=0.9)
    loose = _index().near("dragon scimtar", keep=0.5)
    assert len(loose) > len(tight)
    assert loose[0].key.id == tight[0].key.id


def test_no_more_than_the_asked_for_number_ever_comes_back() -> None:
    assert len(_index().near("dragon", keep=0.1, limit=2)) == 2


def test_asking_for_none_is_answered_with_none() -> None:
    assert _index().near("dragon", limit=0) == ()


def test_a_query_with_nothing_in_it_matches_nothing() -> None:
    assert _index().near("   ") == ()
    assert _index().near("!!!") == ()


def test_the_same_question_is_always_answered_in_the_same_order() -> None:
    index = _index()
    once = [(nearby.key, nearby.score) for nearby in index.near("dragon", keep=0.1)]
    again = [(nearby.key, nearby.score) for nearby in index.near("dragon", keep=0.1)]
    assert once == again


def test_two_names_that_are_equally_close_are_ordered_by_identity() -> None:
    index = NameIndex(((_key(9), "Rune bar"), (_key(2), "Rune bar")))
    assert index.near("rune bar")[0].key.id == 2


def test_the_same_name_twice_is_only_one_thing_to_choose_between() -> None:
    index = NameIndex(((_key(2), "Clue scroll"), (_key(9), "Clue scroll")))
    assert len(index) == 1
    assert len(index.near("clue scrol")) == 1


def test_a_thing_with_no_name_is_never_offered() -> None:
    index = NameIndex(((_key(1), "   "), (_key(2), "Coins")))
    assert len(index) == 1


def test_a_name_that_shares_no_letters_at_all_is_not_compared() -> None:
    assert NameIndex(((_key(1), "Coins"),)).near("zzzz") == ()
