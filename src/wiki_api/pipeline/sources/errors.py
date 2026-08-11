"""Errors an adapter raises, each naming the source record at fault."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.errors import KnowledgeError

if TYPE_CHECKING:
    from collections.abc import Sequence


class AdapterError(KnowledgeError):
    """Base class for anything that stops a source being read into the model."""


class UnknownSourceField(AdapterError):
    """A source grew a field no adapter maps and no adapter declares it ignores."""

    def __init__(self, source: str, field: str, record: str) -> None:
        super().__init__(
            f"{source} record {record} carries {field!r}, which this adapter neither "
            f"maps nor ignores; map it or add it to the ignore list"
        )
        self.source = source
        self.field = field
        self.record = record


class ConflictingRecords(AdapterError):
    """One source declares the same id twice with different content."""

    def __init__(self, source: str, identity: str, first: str, second: str) -> None:
        super().__init__(
            f"{source} declares {identity} twice, as {first!r} and {second!r}; "
            f"an overlay must define which one wins"
        )
        self.source = source
        self.identity = identity
        self.first = first
        self.second = second


class MalformedSourceValue(AdapterError):
    """A packed source value does not have the shape its adapter reads."""

    def __init__(self, source: str, record: str, field: str, detail: str) -> None:
        super().__init__(f"{source} record {record} has a bad {field}: {detail}")
        self.source = source
        self.record = record
        self.field = field
        self.detail = detail


class DriftedVocabulary(AdapterError):
    """A vocabulary read by position no longer matches the list it is read from."""

    def __init__(
        self, source: str, expected: Sequence[str], found: Sequence[str]
    ) -> None:
        moved = [
            f"{at} was {was} and is now {now}"
            for at, (was, now) in enumerate(zip(expected, found, strict=False))
            if was != now
        ]
        super().__init__(
            f"{source} no longer declares what this build reads by position: "
            f"{'; '.join(moved) or f'{len(expected)} names against {len(found)}'}"
        )
        self.source = source
        self.expected = tuple(expected)
        self.found = tuple(found)


class UnallocatedIdentity(AdapterError):
    """A source names something the identity file has never given a number to."""

    def __init__(self, entity_type: str, source_key: str) -> None:
        super().__init__(
            f"no id is allocated for {entity_type} {source_key!r}: "
            f"run the allocation command and review what it adds"
        )
        self.entity_type = entity_type
        self.source_key = source_key


# test cases


def test_every_adapter_error_is_a_knowledge_error() -> None:
    errors = (
        UnknownSourceField("item_configs.json", "sparkle", "4587"),
        ConflictingRecords("item_configs.json", "item:14422", "Scroll", "USDT Slot"),
        MalformedSourceValue("shops.json", "1", "stock", "not three numbers"),
        UnallocatedIdentity("quest", "DEATH_PLATEAU"),
        DriftedVocabulary("WeaponInterface.java", ("BOW",), ("CROSSBOW",)),
    )
    assert all(isinstance(error, AdapterError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_an_unknown_field_says_what_to_do_about_it() -> None:
    error = UnknownSourceField("item_configs.json", "sparkle", "4587")
    assert "sparkle" in str(error)
    assert "ignore list" in str(error)


def test_a_drifted_vocabulary_says_which_position_moved() -> None:
    error = DriftedVocabulary(
        "WeaponInterface.java", ("BOW", "CROSSBOW"), ("BOW", "SLING")
    )
    assert "1 was CROSSBOW and is now SLING" in str(error)
    assert "BOW was BOW" not in str(error)


def test_a_vocabulary_that_changed_length_still_says_so() -> None:
    error = DriftedVocabulary("WeaponInterface.java", ("BOW", "CROSSBOW"), ("BOW",))
    assert "2 names against 1" in str(error)


def test_a_conflict_names_both_records() -> None:
    error = ConflictingRecords("item_configs.json", "item:14422", "Scroll", "USDT Slot")
    assert "Scroll" in str(error)
    assert "USDT Slot" in str(error)
