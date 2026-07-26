"""Readable slugs, derived once and stable across rebuilds so links do not rot."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import TYPE_CHECKING

from wiki_api.domain.errors import SlugCollision
from wiki_api.domain.identity import EntityKey, EntityType

if TYPE_CHECKING:
    from collections.abc import Mapping

_SEPARATORS = re.compile(r"[^a-z0-9]+")
_MAX_PASSES = 4


def slugify(value: str) -> str:
    """Fold a name down to lowercase letters and digits joined by separators."""
    folded = unicodedata.normalize("NFKD", value)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    return _SEPARATORS.sub("-", ascii_only.lower()).strip("-")


def derive_slugs(names: Mapping[EntityKey, str]) -> dict[EntityKey, str]:
    """Give every entity a slug that is unique within its own type."""
    slugs = {
        key: slugify(names[key]) or _fallback(key)
        for key in sorted(names, key=lambda key: (key.type.value, key.id))
    }
    for _ in range(_MAX_PASSES):
        collisions = _collisions(slugs)
        if not collisions:
            return slugs
        for keys in collisions.values():
            for key in keys:
                slugs[key] = f"{slugs[key]}-{key.id}"
    unresolved_type, unresolved_slug = next(iter(_collisions(slugs)))
    raise SlugCollision(f"{unresolved_type.value}/{unresolved_slug}")


def _fallback(key: EntityKey) -> str:
    return f"{key.type.value}-{key.id}"


def _collisions(
    slugs: Mapping[EntityKey, str],
) -> dict[tuple[EntityType, str], list[EntityKey]]:
    grouped: defaultdict[tuple[EntityType, str], list[EntityKey]] = defaultdict(list)
    for key, slug in slugs.items():
        grouped[(key.type, slug)].append(key)
    return {group: keys for group, keys in grouped.items() if len(keys) > 1}


# test cases


def test_slugify_folds_case_punctuation_and_accents() -> None:
    assert slugify("Dragon scimitar") == "dragon-scimitar"
    assert slugify("Shortbow (u)") == "shortbow-u"
    assert slugify("Bone in vinegar!!") == "bone-in-vinegar"
    assert slugify("Café  au   lait") == "cafe-au-lait"
    assert slugify("  --Ancient page--  ") == "ancient-page"
    assert slugify("!!!") == ""


def test_a_unique_name_keeps_the_bare_slug() -> None:
    names = {EntityKey(type=EntityType.ITEM, id=1101): "Iron chainbody"}
    assert derive_slugs(names) == {
        EntityKey(type=EntityType.ITEM, id=1101): "iron-chainbody"
    }


def test_colliding_names_are_all_disambiguated() -> None:
    names = {
        EntityKey(type=EntityType.ITEM, id=4587): "Dragon scimitar",
        EntityKey(type=EntityType.ITEM, id=4588): "Dragon scimitar",
        EntityKey(type=EntityType.ITEM, id=13477): "Dragon scimitar",
    }
    assert set(derive_slugs(names).values()) == {
        "dragon-scimitar-4587",
        "dragon-scimitar-4588",
        "dragon-scimitar-13477",
    }


def test_the_same_name_in_two_types_does_not_collide() -> None:
    names = {
        EntityKey(type=EntityType.ITEM, id=50): "Guard",
        EntityKey(type=EntityType.NPC, id=9): "Guard",
    }
    assert derive_slugs(names) == {
        EntityKey(type=EntityType.ITEM, id=50): "guard",
        EntityKey(type=EntityType.NPC, id=9): "guard",
    }


def test_unnamed_entities_fall_back_to_their_identity() -> None:
    names = {
        EntityKey(type=EntityType.NPC, id=3089): "",
        EntityKey(type=EntityType.NPC, id=3090): "   ",
    }
    assert derive_slugs(names) == {
        EntityKey(type=EntityType.NPC, id=3089): "npc-3089",
        EntityKey(type=EntityType.NPC, id=3090): "npc-3090",
    }


def test_a_name_colliding_with_a_disambiguated_slug_is_resolved() -> None:
    names = {
        EntityKey(type=EntityType.ITEM, id=5): "Foo",
        EntityKey(type=EntityType.ITEM, id=7): "Foo",
        EntityKey(type=EntityType.ITEM, id=9): "Foo 5",
    }
    slugs = derive_slugs(names)
    assert len(set(slugs.values())) == 3


def test_derivation_is_independent_of_input_order() -> None:
    names = {
        EntityKey(type=EntityType.ITEM, id=2677): "Clue scroll",
        EntityKey(type=EntityType.ITEM, id=2678): "Clue scroll",
        EntityKey(type=EntityType.ITEM, id=4587): "Dragon scimitar",
        EntityKey(type=EntityType.NPC, id=50): "King Black Dragon",
    }
    reversed_names = dict(reversed(list(names.items())))
    assert derive_slugs(names) == derive_slugs(reversed_names)


def test_derivation_is_stable_when_an_unrelated_entity_is_added() -> None:
    scimitar = EntityKey(type=EntityType.ITEM, id=4587)
    before = derive_slugs({scimitar: "Dragon scimitar"})
    bones = EntityKey(type=EntityType.ITEM, id=526)
    after = derive_slugs({scimitar: "Dragon scimitar", bones: "Bones"})
    assert before[scimitar] == after[scimitar]
