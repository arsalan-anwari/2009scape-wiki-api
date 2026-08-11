"""Read what one thing was worth over time, a page at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.domain.identity import EntityType
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page
from wiki_api.domain.prices import PriceMovement, PricePoint, moved

if TYPE_CHECKING:
    from datetime import date

    from wiki_api.domain.entity import Entity
    from wiki_api.repository.protocol import KnowledgeRepository


def history(
    repository: KnowledgeRepository,
    entity: Entity,
    *,
    since: date | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> Page[PricePoint]:
    """Page through what this entity was worth, newest last, empty for anything the
    market never recorded.
    """
    if entity.key.type is not EntityType.ITEM:
        return Page[PricePoint](items=(), total=0, limit=limit, offset=offset)
    points = repository.price_history(entity.key.id, since=since)
    return Page[PricePoint](
        items=tuple(points[offset : offset + limit]),
        total=len(points),
        limit=limit,
        offset=offset,
    )


def movement(
    repository: KnowledgeRepository, entity: Entity, *, since: date | None = None
) -> PriceMovement | None:
    """Read which way this entity's worth went over a stretch of the record.

    Anything the market never recorded, and anything that is not traded at all, answers
    with nothing rather than with a change of zero.
    """
    if entity.key.type is not EntityType.ITEM:
        return None
    return moved(repository.price_history(entity.key.id, since=since))


# test cases


def _repository(points: tuple[PricePoint, ...]) -> KnowledgeRepository:
    from datetime import date as day
    from typing import cast

    class Recorded:
        def price_history(
            self, item_id: int, *, since: day | None = None
        ) -> tuple[PricePoint, ...]:
            return tuple(
                point
                for point in points
                if point.item_id == item_id
                and (since is None or point.snapshot_date >= since)
            )

    return cast("KnowledgeRepository", Recorded())


def _item(entity_type: EntityType = EntityType.ITEM) -> Entity:
    from wiki_api.domain.entity import Entity as Thing

    return Thing.model_validate(
        {
            "key": {"type": entity_type.value, "id": 4587},
            "slug": "dragon-scimitar",
            "name": "Dragon scimitar",
            "attributes": {},
            "provenance": {"source": "fixture", "game_version": "test"},
        }
    )


def _points() -> tuple[PricePoint, ...]:
    from datetime import date as day

    from wiki_api.domain.prices import PricePoint as Point

    return tuple(
        Point(item_id=4587, snapshot_date=day(2024, 6, 8 + step), value=100 + step)
        for step in range(5)
    )


def test_a_whole_record_comes_back_oldest_first() -> None:
    page = history(_repository(_points()), _item())
    assert page.total == 5
    assert [point.value for point in page.items] == [100, 101, 102, 103, 104]


def test_a_record_is_paged_like_everything_else() -> None:
    page = history(_repository(_points()), _item(), limit=2, offset=2)
    assert [point.value for point in page.items] == [102, 103]
    assert page.total == 5
    assert page.next_offset == 4


def test_a_thing_that_is_not_traded_at_all_answers_with_nothing() -> None:
    page = history(_repository(_points()), _item(EntityType.NPC))
    assert page.items == ()
    assert page.total == 0


def test_an_item_the_market_never_recorded_answers_with_nothing() -> None:
    page = history(_repository(()), _item())
    assert page.total == 0


def test_a_movement_reads_the_whole_record_it_was_given() -> None:
    went = movement(_repository(_points()), _item())
    assert went is not None
    assert (went.opened, went.closed, went.change) == (100, 104, 4)


def test_a_movement_only_reads_the_stretch_it_was_asked_about() -> None:
    from datetime import date as day

    went = movement(_repository(_points()), _item(), since=day(2024, 6, 10))
    assert went is not None
    assert went.entries == 3
    assert went.opened == 102


def test_a_thing_that_is_not_traded_at_all_never_moved() -> None:
    assert movement(_repository(_points()), _item(EntityType.NPC)) is None


def test_an_item_the_market_never_recorded_never_moved() -> None:
    assert movement(_repository(()), _item()) is None
