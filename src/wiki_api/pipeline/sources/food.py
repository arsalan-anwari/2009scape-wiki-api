"""Read how much an item restores out of the enum that states it.

The game keeps a chain of what a consumable leaves you holding, so only the definition
that offers to eat or drink an item decides whether it is food.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from wiki_api.domain.identity import EntityKey, EntityType
from wiki_api.domain.vocabulary import SourceKind
from wiki_api.pipeline.artifact.overlay import (
    OverlayMode,
    OverlayPrecedence,
    OverlaySource,
)
from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.staging.declared import ITEM_EXTRACT, DeclaredTable

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from wiki_api.pipeline.sources.staged import StagedSources

CONSUMABLES: Final = DeclaredTable(
    enum="Consumables", path="content/data/consumables/Consumables.java"
)
HEALS_ATTRIBUTE: Final = "heals"
CONSUMABLE_COLUMN: Final = "consumable"
CALL_KEY: Final = "call"
ARGUMENTS_KEY: Final = "arguments"
HEALING_CALL: Final = "HealingEffect"
OPTIONS_FIELD: Final = "options"
ID_FIELD: Final = "id"
EATEN: Final = frozenset({"Eat", "Drink"})
UNSTAGED_VERSION: Final = "2009scape@unknown"


def read_food(staged: StagedSources, known: frozenset[EntityKey]) -> SourceOutcome:
    """Patch every item a consumable restores a stated number of hitpoints for."""
    if not staged.has_staged(CONSUMABLES.staged):
        return _outcome(staged, [], [], 0, ())
    eaten = _eaten(staged)
    stated: dict[int, set[int]] = {}
    uneaten = 0
    for item_id, amount in _stated(staged.table(CONSUMABLES).constants):
        if item_id not in eaten:
            uneaten += 1
            continue
        stated.setdefault(item_id, set()).add(amount)
    entities: list[dict[str, Any]] = []
    skipped: list[Skipped] = []
    disputed: list[str] = []
    for item_id, amounts in sorted(stated.items()):
        key = EntityKey(type=EntityType.ITEM, id=item_id)
        if len(amounts) > 1:
            disputed.append(
                f"item {item_id}: {', '.join(str(one) for one in sorted(amounts))}"
            )
            continue
        if key not in known:
            skipped.append(
                Skipped(
                    source=CONSUMABLES.staged,
                    reason=SkipReason.UNKNOWN_TARGET,
                    detail=str(key),
                )
            )
            continue
        entities.append(
            {
                "type": EntityType.ITEM.value,
                "id": item_id,
                "mode": OverlayMode.PATCH.value,
                "attributes": {HEALS_ATTRIBUTE: amounts.pop()},
                "source_ref": f"{CONSUMABLES.filename}#{item_id}",
            }
        )
    return _outcome(staged, entities, skipped, uneaten, tuple(disputed))


def _stated(constants: Sequence[Any]) -> Iterator[tuple[int, int]]:
    """Yield every item id a constant names, with the number it says it restores.

    Only an effect stated outright is read; one wrapped in a combination of effects
    belongs to the combination, not to the food.
    """
    for constant in constants:
        held = constant.values.get(CONSUMABLE_COLUMN)
        if not isinstance(held, dict):
            continue
        arguments = held.get(ARGUMENTS_KEY) or []
        if len(arguments) < 2 or not isinstance(arguments[0], list):
            continue
        amount = _healed(arguments[1])
        if amount is None:
            continue
        for item_id in arguments[0]:
            if isinstance(item_id, int) and not isinstance(item_id, bool):
                yield item_id, amount


def _healed(effect: Any) -> int | None:
    if not isinstance(effect, dict) or effect.get(CALL_KEY) != HEALING_CALL:
        return None
    given = effect.get(ARGUMENTS_KEY) or []
    if len(given) != 1 or not isinstance(given[0], int) or isinstance(given[0], bool):
        return None
    return given[0]


def _eaten(staged: StagedSources) -> frozenset[int]:
    """Every item the game itself offers to eat or drink."""
    if not staged.has_extract(ITEM_EXTRACT):
        return frozenset()
    return frozenset(
        int(record[ID_FIELD])
        for record in staged.extract(ITEM_EXTRACT)
        if EATEN & {one for one in (record.get(OPTIONS_FIELD) or []) if one}
    )


def _outcome(
    staged: StagedSources,
    entities: Sequence[Mapping[str, Any]],
    skipped: Sequence[Skipped],
    uneaten: int,
    disputed: Sequence[str],
) -> SourceOutcome:
    notes = [
        f"{len(entities)} items restore an amount the table states outright",
        f"{uneaten} named ids the game offers no way to eat or drink",
    ]
    notes.extend(f"the table disagrees with itself, {one}" for one in disputed)
    return SourceOutcome(
        source=CONSUMABLES.staged,
        read=_document(staged, entities),
        skipped=tuple(skipped),
        notes=tuple(notes),
    )


def _document(
    staged: StagedSources, entities: Sequence[Mapping[str, Any]]
) -> OverlaySource:
    path = CONSUMABLES.staged
    return OverlaySource.model_validate(
        {
            "origin": path,
            "document": {
                "schema": 1,
                "source": SourceKind.GAME_CODE.value,
                "source_file": path,
                "source_revision": _revision(staged, path),
                "game_version": _game_version(staged, path),
                "precedence": OverlayPrecedence.DECLARED,
                "entities": list(entities),
            },
        }
    )


def _revision(staged: StagedSources, path: str) -> str | None:
    for entry in staged.manifest.files:
        if entry.path == path:
            return entry.source_revision
    return None


def _game_version(staged: StagedSources, path: str) -> str:
    for entry in staged.manifest.files:
        if entry.path == path:
            return str(entry.game_version)
    versions = sorted({str(entry.game_version) for entry in staged.manifest.files})
    return versions[0] if versions else UNSTAGED_VERSION


# test cases


def _table(*rows: tuple[str, dict[str, Any]]) -> Any:
    from wiki_api.pipeline.enums.reader import EnumConstant

    return [EnumConstant(name=name, values=values) for name, values in rows]


def _food(ids: list[int], amount: int) -> dict[str, Any]:
    return {
        CONSUMABLE_COLUMN: {
            CALL_KEY: "Food",
            ARGUMENTS_KEY: [ids, {CALL_KEY: HEALING_CALL, ARGUMENTS_KEY: [amount]}],
        }
    }


def test_an_item_takes_the_number_the_constant_states() -> None:
    assert list(_stated(_table(("SHARK", _food([385], 20))))) == [(385, 20)]


def test_every_id_a_constant_names_takes_the_same_number() -> None:
    read = list(_stated(_table(("KEG", _food([5817, 5815], 5)))))
    assert read == [(5817, 5), (5815, 5)]


def test_an_effect_wrapped_in_a_combination_is_not_read() -> None:
    wrapped = {
        CONSUMABLE_COLUMN: {
            CALL_KEY: "Food",
            ARGUMENTS_KEY: [
                [7178],
                {
                    CALL_KEY: "MultiEffect",
                    ARGUMENTS_KEY: [{CALL_KEY: HEALING_CALL, ARGUMENTS_KEY: [6]}],
                },
            ],
        }
    }
    assert list(_stated(_table(("GARDEN_PIE", wrapped)))) == []


def test_an_effect_that_is_not_a_healing_one_is_not_read() -> None:
    ranged = {
        CONSUMABLE_COLUMN: {
            CALL_KEY: "Food",
            ARGUMENTS_KEY: [
                [3369],
                {CALL_KEY: "RandomHealthEffect", ARGUMENTS_KEY: [5, 7]},
            ],
        }
    }
    assert list(_stated(_table(("THIN_SNAIL", ranged)))) == []


def test_a_constant_naming_one_id_rather_than_a_list_is_not_read() -> None:
    single = {
        CONSUMABLE_COLUMN: {
            CALL_KEY: "FakeConsumable",
            ARGUMENTS_KEY: [3168, ["You really do not want to eat that."]],
        }
    }
    assert list(_stated(_table(("SEAWEED", single)))) == []
