"""Answer every question about the game in one place; a surface calls these and only
shapes what comes back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wiki_api.core import discovery
from wiki_api.core.descriptors import describe_page
from wiki_api.core.resolution import resolve
from wiki_api.core.results import (
    Block,
    BlockResolution,
    Direction,
    EntityResolution,
    EntitySummary,
    Found,
    Match,
    Named,
    PageDescriptor,
    PageResolution,
    SearchResult,
    TooltipResolution,
    TypeInfo,
)
from wiki_api.core.tooltips import preview
from wiki_api.core.walks import BLOCK_PAGE_SIZE, walk
from wiki_api.domain.page import DEFAULT_PAGE_SIZE, Page, SortOrder
from wiki_api.domain.search import NEAR_FLOOR, NEAR_KEEP, NEAR_LIMIT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wiki_api.core.resolution import Reference
    from wiki_api.domain.entity import Entity
    from wiki_api.domain.identity import EntityType
    from wiki_api.domain.manifest import Manifest
    from wiki_api.domain.relationships import RelationshipType
    from wiki_api.repository.protocol import KnowledgeRepository


class KnowledgeService:
    """Answer everything a client can ask, in game terms rather than storage terms."""

    def __init__(
        self,
        repository: KnowledgeRepository,
        *,
        block_size: int = BLOCK_PAGE_SIZE,
    ) -> None:
        self._repository = repository
        self._block_size = block_size

    def about(self) -> Manifest:
        """Report which build of the knowledge base is being served."""
        return self._repository.manifest()

    def resolve(self, reference: Reference) -> EntityResolution:
        """Find the entity a reference names, or say why there isn't one."""
        return resolve(self._repository, reference)

    def get_page(self, reference: Reference) -> PageResolution:
        """Describe a whole page as data."""
        resolution = self.resolve(reference)
        if not isinstance(resolution, Found):
            return resolution
        return Found(
            value=describe_page(
                self._repository,
                resolution.value,
                data_version=self.about().data_version,
                limit=self._block_size,
            )
        )

    def tooltip(self, reference: Reference) -> TooltipResolution:
        """Describe an entity at hover size."""
        resolution = self.resolve(reference)
        if not isinstance(resolution, Found):
            return resolution
        return Found(value=preview(resolution.value))

    def walk(
        self,
        reference: Reference,
        rel: RelationshipType,
        direction: Direction = Direction.FORWARD,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> BlockResolution:
        """One relationship of one entity, in one direction, one page at a time."""
        resolution = self.resolve(reference)
        if not isinstance(resolution, Found):
            return resolution
        return Found(
            value=walk(
                self._repository,
                resolution.value,
                rel,
                direction,
                limit=limit,
                offset=offset,
            )
        )

    def lookup(
        self,
        name: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Named[Entity]:
        """Resolve the thing a caller named, with what else that name could have
        meant.
        """
        return discovery.lookup(self._repository, name, types=types, limit=limit)

    def page_by_name(
        self,
        name: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Named[PageDescriptor]:
        """Describe a whole page for a caller holding a name rather than an
        identity.
        """
        named = self.lookup(name, types=types, limit=limit)
        if not isinstance(named.resolution, Found):
            return Named[PageDescriptor](
                resolution=named.resolution,
                subject=named.subject,
                alternatives=named.alternatives,
            )
        return Named[PageDescriptor](
            resolution=Found(
                value=describe_page(
                    self._repository,
                    named.resolution.value,
                    data_version=self.about().data_version,
                    limit=self._block_size,
                )
            ),
            subject=named.subject,
            alternatives=named.alternatives,
        )

    def walk_by_name(
        self,
        name: str,
        rel: RelationshipType,
        direction: Direction = Direction.FORWARD,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Named[Block]:
        """One relationship of the thing a caller named, one page at a time."""
        named = self.lookup(name, types=types)
        if not isinstance(named.resolution, Found):
            return Named[Block](
                resolution=named.resolution,
                subject=named.subject,
                alternatives=named.alternatives,
            )
        return Named[Block](
            resolution=Found(
                value=walk(
                    self._repository,
                    named.resolution.value,
                    rel,
                    direction,
                    limit=limit,
                    offset=offset,
                )
            ),
            subject=named.subject,
            alternatives=named.alternatives,
        )

    def search(
        self,
        query: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> Page[SearchResult]:
        """Rank whatever matches the words a caller typed."""
        return discovery.search(
            self._repository, query, types=types, limit=limit, offset=offset
        )

    def find(
        self,
        name: str,
        *,
        types: Sequence[EntityType] | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> Match:
        """Decide which one thing a name means, with everything else it matched."""
        return discovery.find(self._repository, name, types=types, limit=limit)

    def near_names(
        self,
        name: str,
        entity_type: EntityType,
        *,
        limit: int | None = None,
        keep: float | None = None,
        floor: float | None = None,
    ) -> Page[SearchResult]:
        """Return the real names a misspelt one may have meant, identity only, so
        whoever asked chooses rather than being answered from a guess.
        """
        return discovery.near_names(
            self._repository,
            name,
            entity_type,
            limit=limit if limit is not None else NEAR_LIMIT,
            keep=keep if keep is not None else NEAR_KEEP,
            floor=floor if floor is not None else NEAR_FLOOR,
        )

    def list_type(
        self,
        entity_type: EntityType,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order: SortOrder = SortOrder.NAME,
    ) -> Page[EntitySummary]:
        """Read one page of an index."""
        return discovery.list_type(
            self._repository, entity_type, limit=limit, offset=offset, order=order
        )

    def describe_types(self) -> tuple[TypeInfo, ...]:
        """Publish what sorts of thing exist and how their values present."""
        return discovery.describe_types()


# test cases


def test_the_service_answers_every_question_the_phase_promised() -> None:
    operations = {name for name in dir(KnowledgeService) if not name.startswith("_")}
    assert operations == {
        "about",
        "resolve",
        "get_page",
        "tooltip",
        "walk",
        "lookup",
        "page_by_name",
        "walk_by_name",
        "search",
        "find",
        "near_names",
        "list_type",
        "describe_types",
    }


def test_a_near_name_answer_is_asked_for_one_sort_of_thing_at_a_time() -> None:
    import inspect

    signature = inspect.signature(KnowledgeService.near_names)
    assert signature.parameters["entity_type"].default is inspect.Parameter.empty
    for tunable in ("limit", "keep", "floor"):
        assert signature.parameters[tunable].default is None


def test_a_name_is_answered_in_one_call_rather_than_two() -> None:
    import inspect

    for operation in (
        KnowledgeService.lookup,
        KnowledgeService.page_by_name,
        KnowledgeService.walk_by_name,
    ):
        assert "name" in inspect.signature(operation).parameters


def test_the_service_holds_nothing_but_the_repository_it_was_given() -> None:
    import inspect

    signature = inspect.signature(KnowledgeService.__init__)
    assert list(signature.parameters) == ["self", "repository", "block_size"]
    assert signature.parameters["block_size"].default == BLOCK_PAGE_SIZE


def test_a_page_block_is_smaller_than_a_full_listing() -> None:
    assert BLOCK_PAGE_SIZE < DEFAULT_PAGE_SIZE
