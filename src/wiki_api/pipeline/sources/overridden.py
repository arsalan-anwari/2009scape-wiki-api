"""What the overlays define, and what each of them expects the source to still say."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from wiki_api.pipeline.artifact.errors import OverlayExpired
from wiki_api.pipeline.artifact.overlay import OverlayMode

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from collections.abc import Set as AbstractSet

    from wiki_api.domain.identity import EntityKey
    from wiki_api.pipeline.artifact.overlay import OverlayExpectation, OverlaySource

NAME_FIELD: Final = "name"


@dataclass(frozen=True)
class Expectation:
    """One overlay's belief about the source, and the document that stated it."""

    origin: str
    stated: OverlayExpectation


@dataclass
class Overridden:
    """The keys the overlays define, each with whatever it expects the source to say."""

    keys: frozenset[EntityKey]
    expectations: Mapping[EntityKey, Expectation]
    met: set[EntityKey] = field(default_factory=set)
    missed: dict[EntityKey, tuple[str, Any, Any]] = field(default_factory=dict)

    @classmethod
    def of(cls, keys: AbstractSet[EntityKey] = frozenset()) -> Overridden:
        """The keys alone, for a caller with no overlay documents to read."""
        return cls(keys=frozenset(keys), expectations={})

    def __contains__(self, key: EntityKey) -> bool:
        return key in self.keys

    def __or__(self, other: frozenset[EntityKey]) -> frozenset[EntityKey]:
        return self.keys | other

    def check(
        self, key: EntityKey, name: str | None, fields: Mapping[str, Any]
    ) -> None:
        """Record whether this source record is the one an overlay was written against.

        `fields` is the record as staged, and an id the source declares twice is
        satisfied by either record.
        """
        expectation = self.expectations.get(key)
        if expectation is None or key in self.met:
            return
        mismatch = _mismatch(expectation.stated, name, fields)
        if mismatch is None:
            self.met.add(key)
        else:
            self.missed[key] = mismatch

    def unmet(self) -> None:
        """Fail the build for the first correction the sources no longer bear out."""
        for key, expectation in self.expectations.items():
            if key in self.met:
                continue
            found = self.missed.get(key) or _nothing_read(expectation.stated)
            raise OverlayExpired(key, expectation.origin, *found)


def overridden_by(overlays: Sequence[OverlaySource]) -> Overridden:
    """Read what the overlays take from the sources, and what they expect to find."""
    keys: set[EntityKey] = set()
    expectations: dict[EntityKey, Expectation] = {}
    for overlay in overlays:
        for entity in overlay.document.entities:
            if entity.mode is not OverlayMode.DEFINE:
                continue
            keys.add(entity.key)
            if entity.expects is not None:
                expectations[entity.key] = Expectation(
                    origin=overlay.origin, stated=entity.expects
                )
    return Overridden(keys=frozenset(keys), expectations=expectations)


def _mismatch(
    stated: OverlayExpectation, name: str | None, fields: Mapping[str, Any]
) -> tuple[str, Any, Any] | None:
    compared: list[tuple[str, Any, Any]] = []
    if stated.name is not None:
        compared.append((NAME_FIELD, stated.name, name))
    compared.extend(
        (column, wanted, fields.get(column))
        for column, wanted in stated.attributes.items()
    )
    differing = (
        (column, wanted, found) for column, wanted, found in compared if wanted != found
    )
    return next(differing, None)


def _nothing_read(stated: OverlayExpectation) -> tuple[str, Any, Any]:
    if stated.name is not None:
        return (NAME_FIELD, stated.name, None)
    column, wanted = next(iter(stated.attributes.items()))
    return (column, wanted, None)


# test cases


def _overlay(*entities: Any) -> OverlaySource:
    from wiki_api.pipeline.artifact.overlay import OverlaySource

    return OverlaySource.model_validate(
        {
            "origin": "corrections.json",
            "document": {
                "schema": 1,
                "source": "overlay",
                "game_version": "test",
                "precedence": 10,
                "entities": list(entities),
            },
        }
    )


def _key(item_id: int) -> EntityKey:
    from wiki_api.domain.identity import EntityKey, EntityType

    return EntityKey(type=EntityType.ITEM, id=item_id)


def _corrected(**expects: Any) -> Overridden:
    return overridden_by(
        [
            _overlay(
                {
                    "type": "item",
                    "id": 13910,
                    "name": "Corrupt platebody",
                    "expects": expects,
                }
            )
        ]
    )


def test_a_definition_takes_its_entity_away_from_the_source() -> None:
    taken = overridden_by([_overlay({"type": "item", "id": 14422, "name": "Pouch"})])
    assert _key(14422) in taken
    assert taken.expectations == {}


def test_a_patch_takes_nothing_away() -> None:
    taken = overridden_by(
        [_overlay({"type": "item", "id": 4587, "mode": "patch", "name": "X"})]
    )
    assert _key(4587) not in taken


def test_a_correction_that_still_matches_the_source_passes() -> None:
    taken = _corrected(attributes={"requirements": "{1,20}}"})
    taken.check(_key(13910), "Corrupt platebody", {"requirements": "{1,20}}"})
    taken.unmet()


def test_a_correction_fails_once_the_source_is_fixed() -> None:
    import pytest

    taken = _corrected(attributes={"requirements": "{1,20}}"})
    taken.check(_key(13910), "Corrupt platebody", {"requirements": "{1,20}"})
    with pytest.raises(OverlayExpired) as caught:
        taken.unmet()
    assert caught.value.field == "requirements"
    assert caught.value.found == "{1,20}"
    assert caught.value.origin == "corrections.json"


def test_a_correction_for_a_record_the_source_dropped_fails() -> None:
    import pytest

    taken = _corrected(name="Corrupt platebody")
    with pytest.raises(OverlayExpired) as caught:
        taken.unmet()
    assert caught.value.found is None


def test_an_id_the_source_declares_twice_is_met_by_either_record() -> None:
    taken = overridden_by(
        [
            _overlay(
                {
                    "type": "item",
                    "id": 14422,
                    "name": "Sacred clay pouch",
                    "expects": {"name": "USDT Slot"},
                }
            )
        ]
    )
    taken.check(_key(14422), "Sacred clay pouch (class 1)", {})
    taken.check(_key(14422), "USDT Slot", {})
    taken.unmet()


def test_a_record_no_overlay_expects_anything_of_is_left_alone() -> None:
    taken = overridden_by([_overlay({"type": "item", "id": 1, "name": "X"})])
    taken.check(_key(1), "anything", {"whatever": True})
    taken.unmet()
