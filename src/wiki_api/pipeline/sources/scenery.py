"""Read the decoded scenery into the things a player finds standing in the world."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import OverlayPrecedence, OverlaySource
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason, text
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.sources.overridden import Overridden
from wiki_api.pipeline.staging.declared import (
    PLACEMENT_EXTRACT,
    SCENERY_EXTRACT,
    DeclaredConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources
    from wiki_api.pipeline.staging.manifest import StagedFile

EXAMINE_CONFIG: Final = DeclaredConfig(name="object_configs.json")
ID_FIELD: Final = "id"
NAME_FIELD: Final = "name"
OPTIONS_FIELD: Final = "options"
MEMBERS_FIELD: Final = "members_only"
SIZE_X_FIELD: Final = "size_x"
SIZE_Y_FIELD: Final = "size_y"
OBJECT_ID_FIELD: Final = "object_id"
IDS_FIELD: Final = "ids"
EXAMINE_FIELD: Final = "examine"
PLACEMENT_ATTRIBUTE: Final = "placement_count"
UNSTAGED_VERSION: Final = "2009scape@unknown"
EXAMINE_NOTE: Final = (
    "the name and the shape come from the cache, the examine text from "
    "object_configs.json"
)


def read_scenery(staged: StagedSources, overridden: Overridden) -> SourceOutcome:
    """Turn every named thing the world actually holds into an entity."""
    if not staged.has_extract(SCENERY_EXTRACT):
        return SourceOutcome(
            source=SCENERY_EXTRACT.staged,
            read=_document(staged, ()),
            notes=("nothing staged",),
        )
    standing = placement_counts(staged)
    examine = _examine_by_id(staged)
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    read = 0
    for record in staged.stream(SCENERY_EXTRACT):
        read += 1
        object_id = int(record[ID_FIELD])
        key = EntityKey(type=EntityType.SCENERY, id=object_id)
        name = text(record.get(NAME_FIELD)) or ""
        placements = standing.get(object_id, 0)
        reason = _left_out(key, name, placements, overridden)
        if reason is not None:
            if reason is SkipReason.OVERRIDDEN:
                overridden.check(key, name, record)
            skipped.append(
                Skipped(source=SCENERY_EXTRACT.staged, reason=reason, detail=str(key))
            )
            continue
        entities.append(
            {
                "type": EntityType.SCENERY.value,
                "id": object_id,
                "name": name,
                "description": examine.get(object_id),
                "source_ref": f"{SCENERY_EXTRACT.staged}#{object_id}",
                "attributes": _attributes(record, placements),
            }
        )
    return SourceOutcome(
        source=SCENERY_EXTRACT.staged,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=(
            f"{read} definitions read, {len(standing)} of them placed",
            EXAMINE_NOTE,
        ),
    )


def placement_counts(staged: StagedSources) -> Mapping[int, int]:
    """How many of each thing stand in the world, counted over every placement."""
    if not staged.has_extract(PLACEMENT_EXTRACT):
        return {}
    counted: Counter[int] = Counter()
    for record in staged.stream(PLACEMENT_EXTRACT):
        counted[int(record[OBJECT_ID_FIELD])] += 1
    return counted


def _left_out(
    key: EntityKey, name: str, placements: int, overridden: Overridden
) -> SkipReason | None:
    if key in overridden:
        return SkipReason.OVERRIDDEN
    if not name:
        return SkipReason.UNNAMED
    if placements == 0:
        return SkipReason.NO_PLACE
    return None


def _attributes(record: Mapping[str, Any], placements: int) -> dict[str, Any]:
    options = [text(option) for option in record.get(OPTIONS_FIELD) or ()]
    kept: dict[str, Any] = {PLACEMENT_ATTRIBUTE: placements}
    named = [option for option in options if option]
    if named:
        kept[OPTIONS_FIELD] = named
    if record.get(MEMBERS_FIELD) is not None:
        kept["members"] = bool(record[MEMBERS_FIELD])
    for field in (SIZE_X_FIELD, SIZE_Y_FIELD):
        if record.get(field) is not None:
            kept[field] = int(record[field])
    return kept


def _examine_by_id(staged: StagedSources) -> Mapping[int, str]:
    found: dict[int, str] = {}
    for record in staged.records(EXAMINE_CONFIG):
        examine = text(record.get(EXAMINE_FIELD))
        if examine is None:
            continue
        for part in str(record.get(IDS_FIELD, "")).split(","):
            if part.strip().isdigit():
                found.setdefault(int(part), examine)
    return found


def _staged_entry(staged: StagedSources) -> StagedFile | None:
    return next(
        (
            entry
            for entry in staged.manifest.files
            if entry.path == SCENERY_EXTRACT.staged
        ),
        None,
    )


def _game_version(staged: StagedSources) -> str:
    entry = _staged_entry(staged)
    if entry is not None:
        return str(entry.game_version)
    versions = sorted({str(entry.game_version) for entry in staged.manifest.files})
    return versions[0] if versions else UNSTAGED_VERSION


def _source_revision(staged: StagedSources) -> str | None:
    entry = _staged_entry(staged)
    return None if entry is None else str(entry.source_revision or "") or None


def _document(
    staged: StagedSources, entities: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    return OverlaySource.model_validate(
        {
            "origin": SCENERY_EXTRACT.staged,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CACHE.value,
                "source_file": SCENERY_EXTRACT.staged,
                "source_revision": _source_revision(staged),
                "game_version": _game_version(staged),
                "precedence": OverlayPrecedence.DECODED,
                "entities": list(entities),
            },
        }
    )


# test cases


def _staged(tmp_path: Any, scenery: list[dict[str, Any]], **extra: Any) -> Any:
    import gzip
    import json

    from tests.sources import staged_from

    placements = extra.pop("placements", [])
    examine = extra.pop("examine", [])
    written: dict[str, Any] = {
        SCENERY_EXTRACT.staged: json.dumps(scenery),
        PLACEMENT_EXTRACT.staged: gzip.compress(
            "\n".join(json.dumps(record) for record in placements).encode("utf-8")
        ),
        EXAMINE_CONFIG.staged: json.dumps(examine),
    }
    return staged_from(
        tmp_path,
        written,
        revisions={SCENERY_EXTRACT.staged: "index 16 revision 330"},
    )


def test_a_named_thing_standing_in_the_world_becomes_an_entity(tmp_path: Any) -> None:
    outcome = read_scenery(
        _staged(
            tmp_path,
            [
                {
                    "id": 4306,
                    "name": "Furnace",
                    "size_x": 2,
                    "size_y": 3,
                    "members_only": False,
                    "options": ["Smelt", None],
                }
            ],
            placements=[{"object_id": 4306}, {"object_id": 4306}],
            examine=[{"examine": "Hot stuff.", "ids": "4306,4307"}],
        ),
        Overridden.of(),
    )
    entity = outcome.read.document.entities[0]
    assert entity.name == "Furnace"
    assert entity.description == "Hot stuff."
    assert entity.attributes["placement_count"] == 2
    assert entity.attributes["options"] == ["Smelt"]
    assert entity.attributes["size_x"] == 2
    assert entity.attributes["members"] is False


def test_a_definition_nobody_placed_is_counted_rather_than_published(
    tmp_path: Any,
) -> None:
    outcome = read_scenery(
        _staged(tmp_path, [{"id": 4306, "name": "Furnace"}]), Overridden.of()
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"no_place": 1}


def test_an_unnamed_definition_is_counted_rather_than_published(tmp_path: Any) -> None:
    outcome = read_scenery(
        _staged(
            tmp_path,
            [{"id": 7, "name": None}],
            placements=[{"object_id": 7}],
        ),
        Overridden.of(),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"unnamed": 1}


def test_an_overlay_that_defines_the_thing_takes_it_from_the_source(
    tmp_path: Any,
) -> None:
    outcome = read_scenery(
        _staged(
            tmp_path,
            [{"id": 4306, "name": "Furnace"}],
            placements=[{"object_id": 4306}],
        ),
        Overridden.of({EntityKey(type=EntityType.SCENERY, id=4306)}),
    )
    assert outcome.entities == 0
    assert outcome.skipped_by_reason() == {"overridden": 1}


def test_the_document_carries_the_revision_it_was_decoded_from(tmp_path: Any) -> None:
    outcome = read_scenery(
        _staged(
            tmp_path,
            [{"id": 4306, "name": "Furnace"}],
            placements=[{"object_id": 4306}],
        ),
        Overridden.of(),
    )
    assert outcome.read.document.source_revision == "index 16 revision 330"
    assert outcome.read.document.source is SourceKind.GAME_CACHE


def test_a_build_with_no_staged_cache_reads_nothing(tmp_path: Any) -> None:
    from tests.sources import staged_from

    staged = staged_from(tmp_path, {"configs/item_configs.json": "[]"})
    assert read_scenery(staged, Overridden.of()).entities == 0


def test_placements_are_counted_by_the_thing_they_place(tmp_path: Any) -> None:
    staged = _staged(
        tmp_path,
        [],
        placements=[
            {"object_id": 1276},
            {"object_id": 1276},
            {"object_id": 4306},
        ],
    )
    assert placement_counts(staged) == {1276: 2, 4306: 1}
