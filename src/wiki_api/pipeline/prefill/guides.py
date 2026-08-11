"""Read the community quest guides into the requirements the game states nowhere.

This proposes rather than publishes, which is why it sits beside the command that
writes overlays rather than beside the adapters the build reads.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.relationships import RelationshipType
from wiki_api.domain.vocabulary import Skill, SourceKind
from wiki_api.pipeline.artifact.overlay import (
    OverlayMode,
    OverlayPrecedence,
    OverlaySource,
)
from wiki_api.pipeline.prefill.saved import saved_pages
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.journal import folded
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import QUEST_PAGES

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources
    from wiki_api.pipeline.wiki.pages import WikiPage, WikiSection

REQUIREMENT_SECTIONS: Final = frozenset(
    {
        "requirements",
        "required",
        "items_required",
        "required_items",
        "skill_requirements",
        "quest_requirements",
    }
)
DIFFICULTY_SECTIONS: Final = frozenset({"ratings", "start_point", "start"})
LABEL: Final = re.compile(
    r"\b(Skills|Quests|Items|Required Items|Recommended Skills|Recommended|"
    r"Suggested items|Other)\b\s*:?",
    re.IGNORECASE,
)
SKILL_LEVEL: Final = re.compile(
    r"(?:level\s+)?(\d{1,2})\s*\+?\s*("
    + "|".join(skill.value for skill in Skill)
    + r")\b",
    re.IGNORECASE,
)
SKILLS_CLAUSE: Final = "skills"
QUESTS_CLAUSE: Final = "quests"
NAMESPACE_SEPARATOR: Final = "/"
SHORTEST_NAME: Final = 7
MAX_LEVEL: Final = 99


def read_quest_guides(
    staged: StagedSources, quests: Mapping[str, EntityKey], known: frozenset[EntityKey]
) -> SourceOutcome:
    """Turn each guide's requirement clauses into skills a quest asks for and links.

    `quests` is keyed by the folded quest name, which is how a page is matched to the
    quest it is about; a page that matches nothing is counted rather than guessed at.
    """
    pages = saved_pages(staged, QUEST_PAGES)
    entities: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    for page in pages:
        subject = _subject(page, quests)
        if subject is None:
            skipped.append(
                Skipped(
                    source=QUEST_PAGES.staged,
                    reason=SkipReason.UNKNOWN_SUBJECT,
                    detail=page.slug,
                )
            )
            continue
        clauses = _clauses(page)
        needed = _skills(clauses.get(SKILLS_CLAUSE, ""))
        if needed:
            entities.append(
                {
                    "type": EntityType.QUEST.value,
                    "id": subject.id,
                    "mode": OverlayMode.PATCH.value,
                    "attributes": {"requirements": needed},
                    "source_ref": f"{QUEST_PAGES.staged}#{page.slug}",
                }
            )
        edges.extend(
            _required(
                page, subject, clauses.get(QUESTS_CLAUSE, ""), quests, known, skipped
            )
        )
    return SourceOutcome(
        source=QUEST_PAGES.staged,
        read=_document(staged, entities, edges),
        skipped=tuple(skipped),
        notes=(
            f"{len(pages)} guides read",
            f"{len(entities)} quests carry the skills a guide states",
            f"{len(edges)} requirement links written",
        ),
    )


def _subject(page: WikiPage, quests: Mapping[str, EntityKey]) -> EntityKey | None:
    """Which declared quest a page is about, over the spellings a slug is written in."""
    plain = page.slug.replace("_", " ")
    for spelling in (plain, f"the {plain}", f"{plain} quest"):
        found = quests.get(folded(spelling))
        if found is not None:
            return found
    return None


def _clauses(page: WikiPage) -> dict[str, str]:
    """Split each requirement section at its own labels, so a heading owns its list.

    A guide writes `Skills: 20 Crafting ... Recommended Skills 49 Crafting`, so reading
    the whole section would publish what it says is optional.
    """
    found: dict[str, str] = {}
    for section in page.sections_named(REQUIREMENT_SECTIONS):
        for name, text in _labelled(section):
            found.setdefault(name, text)
    return found


def _labelled(section: WikiSection) -> Iterator[tuple[str, str]]:
    marks = list(LABEL.finditer(section.text))
    for position, mark in enumerate(marks):
        end = marks[position + 1].start() if position + 1 < len(marks) else None
        yield mark.group(1).lower(), section.text[mark.end() : end].strip()


def _skills(clause: str) -> list[dict[str, Any]]:
    """The highest level each skill is asked for, so one skill is stated once."""
    highest: dict[str, int] = {}
    for level, name in SKILL_LEVEL.findall(clause):
        wanted = int(level)
        if not 1 <= wanted <= MAX_LEVEL:
            continue
        key = name.lower()
        highest[key] = max(highest.get(key, 0), wanted)
    return [
        {"skill": skill, "level": level} for skill, level in sorted(highest.items())
    ]


def _required(
    page: WikiPage,
    subject: EntityKey,
    clause: str,
    quests: Mapping[str, EntityKey],
    known: frozenset[EntityKey],
    skipped: list[Skipped],
) -> Iterator[dict[str, Any]]:
    for target in _prerequisites(page, subject, clause, quests):
        yield _edge(page, subject, target, "completed")
    for item_id in _items(page):
        target = EntityKey(type=EntityType.ITEM, id=item_id)
        if target not in known:
            skipped.append(
                Skipped(
                    source=QUEST_PAGES.staged,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(target),
                )
            )
            continue
        yield _edge(page, subject, target, "carried")


def _prerequisites(
    page: WikiPage,
    subject: EntityKey,
    clause: str,
    quests: Mapping[str, EntityKey],
) -> list[EntityKey]:
    """The quests a guide names, taken from its own link and from its quests clause."""
    found: dict[str, EntityKey] = {}
    for link in _linked(page):
        target = _subject_of(link, quests)
        if target is not None and target != subject:
            found[str(target)] = target
    blob = folded(clause)
    for name, target in quests.items():
        if len(name) >= SHORTEST_NAME and name in blob and target != subject:
            found[str(target)] = target
    return [found[key] for key in sorted(found)]


def _linked(page: WikiPage) -> Iterator[str]:
    for section in page.sections_named(REQUIREMENT_SECTIONS):
        for link in section.page_links:
            namespace, _, slug = link.partition(NAMESPACE_SEPARATOR)
            if namespace == QUEST_PAGES.namespace and slug != page.slug:
                yield slug


def _subject_of(slug: str, quests: Mapping[str, EntityKey]) -> EntityKey | None:
    plain = slug.replace("_", " ")
    for spelling in (plain, f"the {plain}", f"{plain} quest"):
        found = quests.get(folded(spelling))
        if found is not None:
            return found
    return None


def _items(page: WikiPage) -> list[int]:
    found: dict[int, None] = {}
    for section in page.sections_named(REQUIREMENT_SECTIONS):
        for item_id in section.item_ids:
            found[item_id] = None
    return list(found)


def _edge(
    page: WikiPage, subject: EntityKey, target: EntityKey, kind: str
) -> dict[str, Any]:
    return {
        "src": str(subject),
        "rel": RelationshipType.REQUIRES.value,
        "dst": str(target),
        "attributes": {"kind": kind},
        "source_ref": f"{QUEST_PAGES.staged}#{page.slug}",
    }


def _document(
    staged: StagedSources,
    entities: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": QUEST_PAGES.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.COMMUNITY_WIKI.value,
                "source_file": QUEST_PAGES.staged,
                "game_version": str(staged.version_of(QUEST_PAGES.staged)),
                "precedence": OverlayPrecedence.PROPOSED,
                "entities": list(entities),
                "edges": list(edges),
            },
        }
    )


# test cases


def _staged(tmp_path: Any, pages: list[dict[str, Any]]) -> StagedSources:
    import json

    from tests.sources import staged_from

    return staged_from(
        tmp_path,
        {
            QUEST_PAGES.staged: json.dumps(
                {"namespace": QUEST_PAGES.namespace, "pages": pages}
            )
        },
    )


def _page(slug: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slug": slug,
        "namespace": QUEST_PAGES.namespace,
        "title": slug,
        "sections": [
            {
                "heading_id": one["heading_id"],
                "heading": one.get("heading", ""),
                "text": one.get("text", ""),
                "item_ids": one.get("item_ids", []),
                "page_links": one.get("page_links", []),
            }
            for one in sections
        ],
    }


DESERT: Final = EntityKey(type=EntityType.QUEST, id=1)
PRIEST: Final = EntityKey(type=EntityType.QUEST, id=2)
QUESTS: Final = {
    folded("Desert Treasure"): DESERT,
    folded("Priest in Peril"): PRIEST,
}


def test_a_guide_states_the_skills_a_quest_asks_for(tmp_path: Any) -> None:
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [
                        {
                            "heading_id": "required",
                            "text": "Skills: 50 Firemaking 53 Thieving "
                            "Quests: None Items: Ashes",
                        }
                    ],
                )
            ],
        ),
        QUESTS,
        frozenset(),
    )
    patch = outcome.read.document.entities[0]
    assert patch.id == DESERT.id
    assert patch.attributes["requirements"] == [
        {"skill": "firemaking", "level": 50},
        {"skill": "thieving", "level": 53},
    ]


def test_a_skill_a_guide_only_recommends_is_left_out(tmp_path: Any) -> None:
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [
                        {
                            "heading_id": "required",
                            "text": "Skills 20 Crafting 49 Firemaking "
                            "Recommended Skills 49 Crafting would help",
                        }
                    ],
                )
            ],
        ),
        QUESTS,
        frozenset(),
    )
    assert outcome.read.document.entities[0].attributes["requirements"] == [
        {"skill": "crafting", "level": 20},
        {"skill": "firemaking", "level": 49},
    ]


def test_a_quest_a_guide_names_in_its_quests_clause_becomes_a_link(
    tmp_path: Any,
) -> None:
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [
                        {
                            "heading_id": "required",
                            "text": "Skills: 50 Magic Quests: Priest in Peril "
                            "Items: Ashes",
                        }
                    ],
                )
            ],
        ),
        QUESTS,
        frozenset(),
    )
    edge = outcome.read.document.edges[0]
    assert edge.src == DESERT
    assert edge.dst == PRIEST
    assert edge.attributes["kind"] == "completed"


def test_a_quest_named_outside_the_quests_clause_is_not_a_requirement(
    tmp_path: Any,
) -> None:
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [
                        {
                            "heading_id": "required",
                            "text": "Skills: 50 Magic Quests: None "
                            "Items: a rope from Priest in Peril",
                        }
                    ],
                )
            ],
        ),
        QUESTS,
        frozenset(),
    )
    assert outcome.read.document.edges == ()


def test_an_item_a_guide_pictures_becomes_a_link_when_the_item_is_declared(
    tmp_path: Any,
) -> None:
    milk = EntityKey(type=EntityType.ITEM, id=1927)
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [{"heading_id": "requirements", "item_ids": [1927, 9999]}],
                )
            ],
        ),
        QUESTS,
        frozenset({milk}),
    )
    assert [edge.dst for edge in outcome.read.document.edges] == [milk]
    assert outcome.skipped_by_reason() == {"unknown_target": 1}


def test_a_guide_for_a_quest_nothing_declares_is_counted(tmp_path: Any) -> None:
    outcome = read_quest_guides(
        _staged(tmp_path, [_page("quest_experience_by_skill", [])]), QUESTS, frozenset()
    )
    assert outcome.read.document.entities == ()
    assert outcome.skipped_by_reason() == {"unknown_subject": 1}


def test_a_guide_never_makes_a_quest_require_itself(tmp_path: Any) -> None:
    outcome = read_quest_guides(
        _staged(
            tmp_path,
            [
                _page(
                    "desert_treasure",
                    [
                        {
                            "heading_id": "required",
                            "text": "Quests: Desert Treasure",
                            "page_links": ["quest_guides/desert_treasure"],
                        }
                    ],
                )
            ],
        ),
        QUESTS,
        frozenset(),
    )
    assert outcome.read.document.edges == ()


def test_the_facts_a_guide_gives_say_they_came_from_the_wiki(tmp_path: Any) -> None:
    outcome = read_quest_guides(_staged(tmp_path, []), QUESTS, frozenset())
    assert outcome.read.document.source is SourceKind.COMMUNITY_WIKI
