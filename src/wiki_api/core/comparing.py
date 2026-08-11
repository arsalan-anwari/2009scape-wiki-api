"""Answer a question whose subject is a number rather than a name."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core.results import Compared, Found, Row, Uncomparable
from wiki_api.core.values import compared_values
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page
from wiki_api.domain.query import (
    Comparable,
    Comparison,
    Condition,
    Ordering,
    comparable_of,
    understood,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.core.results import ComparisonResolution
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityType
    from wiki_api.repository.protocol import KnowledgeRepository


def comparable(entity_type: EntityType) -> tuple[Comparable, ...]:
    """Every value of one type a caller may put a number against."""
    return comparable_of(entity_type)


def compare(
    repository: KnowledgeRepository,
    entity_type: EntityType,
    *,
    holds: str | None = None,
    how: Comparison = Comparison.AT_LEAST,
    number: float = 0.0,
    ordered_by: str | None = None,
    descending: bool = False,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> ComparisonResolution:
    """Page through the entities of one type whose stored number answers the question.

    Anything not carrying a value being compared or sorted on is left out of the answer
    and out of the total, because it is not a smaller one.
    """
    if holds is None and ordered_by is None:
        return Uncomparable(asked="", offered=_offered(entity_type))
    held = _resolved(entity_type, holds)
    sorted_by = _resolved(entity_type, ordered_by)
    if isinstance(held, str):
        return Uncomparable(asked=held, offered=_offered(entity_type))
    if isinstance(sorted_by, str):
        return Uncomparable(asked=sorted_by, offered=_offered(entity_type))
    where = (
        () if held is None else (Condition(path=held.path, compare=how, value=number),)
    )
    order = (
        None
        if sorted_by is None
        else Ordering(path=sorted_by.path, descending=descending)
    )
    page = repository.list_by_attribute(
        entity_type, where=where, order=order, limit=limit, offset=offset
    )
    shown = tuple(one for one in (held, sorted_by) if one is not None)
    return Found(
        value=Compared(
            type=entity_type,
            where=where,
            order=order,
            rows=Page[Row](
                items=tuple(_row(entity, shown) for entity in page.items),
                total=page.total,
                limit=page.limit,
                offset=page.offset,
            ),
        )
    )


def _resolved(entity_type: EntityType, wanted: str | None) -> Comparable | str | None:
    """What a caller's words meant, or those same words back when they meant nothing."""
    if wanted is None:
        return None
    return understood(entity_type, wanted) or wanted


def _offered(entity_type: EntityType) -> tuple[str, ...]:
    return tuple(one.spec.label for one in comparable_of(entity_type))


def _row(entity: Entity, shown: Sequence[Comparable]) -> Row:
    return Row(
        link=entity.to_link(),
        type=entity.type,
        attributes=compared_values(entity, shown),
    )


# test cases


def _scimitar() -> Entity:
    from wiki_api.domain.entity import Entity as Thing

    return Thing.model_validate(
        {
            "key": {"type": "item", "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {
                "ge_buy_limit": 10,
                "weight": 1.8,
                "bonuses": [8, 67, -2, 0, 0, 0, 1, 0, 0, 0, 0, 66, 0, 0, 0],
            },
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )


def _repository() -> tuple[KnowledgeRepository, list[dict[str, object]]]:
    from typing import cast

    from wiki_api.domain.entity import Entity as Thing
    from wiki_api.domain.identity import EntityType as Sort

    asked: list[dict[str, object]] = []
    found = _scimitar()

    class Listing:
        def list_by_attribute(
            self,
            entity_type: Sort,
            *,
            where: Sequence[Condition] = (),
            order: Ordering | None = None,
            limit: int = DEFAULT_PAGE_SIZE,
            offset: int = 0,
        ) -> Page[Thing]:
            asked.append({"where": list(where), "order": order})
            return Page[Thing](items=(found,), total=1, limit=limit, offset=offset)

    return cast("KnowledgeRepository", Listing()), asked


def test_words_the_registry_does_not_know_are_answered_with_what_it_does() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, asked = _repository()
    answered = compare(repository, Sort.ITEM, holds="how shiny it is")
    assert isinstance(answered, Uncomparable)
    assert answered.asked == "how shiny it is"
    assert answered.offered
    assert asked == []


def test_asking_nothing_compares_nothing() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, asked = _repository()
    answered = compare(repository, Sort.ITEM)
    assert isinstance(answered, Uncomparable)
    assert answered.asked == ""
    assert asked == []


def test_words_the_registry_knows_reach_storage_as_a_declared_path() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, asked = _repository()
    compare(
        repository,
        Sort.ITEM,
        holds="Strength bonus",
        how=Comparison.MORE_THAN,
        number=100,
        ordered_by="Buy limit",
        descending=True,
    )
    condition = asked[0]["where"]
    assert isinstance(condition, list)
    assert condition[0].path == "bonuses.strength"
    assert asked[0]["order"] == Ordering(path="ge_buy_limit", descending=True)


def test_a_row_shows_every_value_the_question_named_and_nothing_else() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, _ = _repository()
    answered = compare(
        repository, Sort.ITEM, holds="strength bonus", ordered_by="weight"
    )
    assert isinstance(answered, Found)
    shown = {
        value.label: value.value for value in answered.value.rows.items[0].attributes
    }
    assert shown == {"Strength bonus": 66, "Weight": 1.8}


def test_the_question_comes_back_beside_the_answer() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, _ = _repository()
    answered = compare(
        repository, Sort.ITEM, holds="buy limit", how=Comparison.AT_LEAST, number=10
    )
    assert isinstance(answered, Found)
    assert answered.value.where[0].compare is Comparison.AT_LEAST
    assert answered.value.where[0].value == 10
    assert answered.value.order is None


def test_a_value_of_another_sort_of_thing_is_not_understood() -> None:
    from wiki_api.domain.identity import EntityType as Sort

    repository, _ = _repository()
    answered = compare(repository, Sort.QUEST, holds="strength bonus")
    assert isinstance(answered, Uncomparable)
