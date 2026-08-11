"""Write the quest overlays a person is meant to finish, filled in as far as the
community wiki goes.

Each file is written once and then owned by whoever edits it; a later run leaves an
existing file alone unless told not to.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import (
    OVERLAY_SCHEMA,
    OverlayMode,
    OverlayPrecedence,
)
from wiki_api.pipeline.prefill.guides import DIFFICULTY_SECTIONS, read_quest_guides
from wiki_api.pipeline.prefill.saved import saved_pages
from wiki_api.pipeline.sources.journal import folded
from wiki_api.pipeline.staging.declared import QUEST_PAGES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from wiki_api.domain.identity import EntityKey
    from wiki_api.pipeline.artifact.overlay import OverlayEdge
    from wiki_api.pipeline.sources.staged import StagedSources

RATING: Final = re.compile(r"\b(?:Difficulty|Length)\s*:\s*[A-Za-z ]{3,20}")
REQUIREMENTS_FILE: Final = "05_quest_requirements.json"
DETAIL_FILE: Final = "04_quest_detail.json"
JSON_INDENT: Final = 2
UNRATED: Final[Mapping[str, Any]] = {
    "difficulty": None,
    "length": None,
    "series": None,
}


def requirements_overlay(
    staged: StagedSources,
    quests: Mapping[str, EntityKey],
    known: frozenset[EntityKey],
    names: Mapping[int, str],
) -> dict[str, Any]:
    """Every quest's requirements, filled in wherever a guide states them clearly."""
    outcome = read_quest_guides(staged, quests, known)
    stated = {entity.id: entity.attributes for entity in outcome.read.document.entities}
    entities = [
        {
            "type": EntityType.QUEST.value,
            "id": key.id,
            "mode": OverlayMode.PATCH.value,
            "attributes": stated.get(key.id, {"requirements": None}),
            "source_ref": _source_ref(names.get(key.id, ""), key.id in stated),
        }
        for key in sorted(set(quests.values()), key=lambda key: key.id)
    ]
    return _document(entities, _readable(outcome.read.document.edges))


def detail_overlay(
    staged: StagedSources, quests: Mapping[str, EntityKey], names: Mapping[int, str]
) -> dict[str, Any]:
    """Every quest's difficulty, length and series, left blank with the wiki's claim
    written beside it, because measuring those ratings showed they do not hold up.
    """
    claimed = _claims(staged, quests)
    entities = [
        {
            "type": EntityType.QUEST.value,
            "id": key.id,
            "mode": OverlayMode.PATCH.value,
            "attributes": dict(UNRATED),
            "source_ref": claimed.get(key.id, f"authored. {names.get(key.id, '')}"),
        }
        for key in sorted(set(quests.values()), key=lambda key: key.id)
    ]
    return _document(entities, ())


def _claims(staged: StagedSources, quests: Mapping[str, EntityKey]) -> dict[int, str]:
    """What each guide says about how hard and how long its quest is, as a note."""
    by_slug = {}
    for page in saved_pages(staged, QUEST_PAGES):
        said = " ".join(
            found.group(0)
            for section in page.sections_named(DIFFICULTY_SECTIONS)
            for found in RATING.finditer(section.text)
        )
        if said:
            by_slug[page.slug] = said
    found: dict[int, str] = {}
    for slug, said in by_slug.items():
        plain = slug.replace("_", " ")
        for spelling in (plain, f"the {plain}", f"{plain} quest"):
            key = quests.get(folded(spelling))
            if key is not None:
                found[key.id] = f"authored. {QUEST_PAGES.staged}#{slug} says {said}"
                break
    return found


def _source_ref(name: str, stated: bool) -> str:
    if stated:
        return f"read from {QUEST_PAGES.staged}, check it before trusting it"
    return f"authored. no guide states requirements for {name}"


def _readable(edges: Sequence[OverlayEdge]) -> list[dict[str, Any]]:
    """Write each link the compact way a person editing the file would write it."""
    return [
        {
            "src": str(edge.src),
            "rel": edge.rel.value,
            "dst": str(edge.dst),
            "attributes": edge.attributes,
            "source_ref": edge.source_ref or "",
        }
        for edge in edges
    ]


def _document(
    entities: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schema": OVERLAY_SCHEMA,
        "source": SourceKind.OVERLAY.value,
        "source_file": QUEST_PAGES.staged,
        "game_version": "authored",
        "precedence": OverlayPrecedence.AUTHORED,
        "entities": list(entities),
        "edges": list(edges),
    }


def written(target: Path, document: Mapping[str, Any], *, force: bool) -> str:
    """Write one overlay, leaving a file somebody has already edited alone."""
    if target.exists() and not force:
        return f"{target.name} is already written, left alone"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(document, indent=JSON_INDENT, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    told = f"{target.name}: {len(document['entities'])} to fill in"
    links = len(document.get("edges", ()))
    return told if not links else f"{told}, {links} links"


# test cases


def test_a_quest_no_guide_covers_still_gets_a_line_to_fill_in() -> None:
    from wiki_api.domain.identity import EntityKey

    quests = {"cooks assistant": EntityKey.parse("quest:3")}
    document = _document(
        [
            {
                "type": "quest",
                "id": 3,
                "mode": "patch",
                "attributes": {"requirements": None},
                "source_ref": _source_ref("Cook's Assistant", stated=False),
            }
        ],
        (),
    )
    assert document["entities"][0]["id"] == 3
    assert "no guide states" in document["entities"][0]["source_ref"]
    assert quests


def test_a_requirement_read_from_a_guide_says_where_it_came_from() -> None:
    assert "check it before trusting it" in _source_ref("Desert Treasure", stated=True)


def test_an_unrated_quest_states_every_field_it_is_waiting_for() -> None:
    assert set(UNRATED) == {"difficulty", "length", "series"}
    assert all(value is None for value in UNRATED.values())


def test_a_document_declares_itself_an_overlay_that_outranks_a_source() -> None:
    document = _document((), ())
    assert document["source"] == "overlay"
    assert document["precedence"] == OverlayPrecedence.AUTHORED


def test_an_overlay_somebody_has_edited_is_not_written_over(tmp_path: Path) -> None:
    target = tmp_path / DETAIL_FILE
    target.write_text("edited by hand", encoding="utf-8")
    told = written(target, _document((), ()), force=False)
    assert "left alone" in told
    assert target.read_text(encoding="utf-8") == "edited by hand"


def test_an_overlay_can_be_written_over_when_asked(tmp_path: Path) -> None:
    target = tmp_path / DETAIL_FILE
    target.write_text("edited by hand", encoding="utf-8")
    written(target, _document((), ()), force=True)
    assert json.loads(target.read_text(encoding="utf-8"))["schema"] == OVERLAY_SCHEMA
