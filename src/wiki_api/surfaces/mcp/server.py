"""Assemble the surface an agent talks to: the tools written out here, plus one built
from the registry for every way a link can be followed.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Final

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from wiki_api.config import Settings, get_settings
from wiki_api.core import KnowledgeService
from wiki_api.domain.identity import EntityType
from wiki_api.domain.manifest import Manifest
from wiki_api.domain.page import MAX_PAGE_SIZE
from wiki_api.domain.query import Comparison
from wiki_api.domain.search import MOST_NEAR_LIMIT
from wiki_api.repository.provider import RepositoryProvider
from wiki_api.surfaces.mcp.answers import (
    Answer,
    about_movement,
    about_ranking,
    about_related,
    about_thing,
)
from wiki_api.surfaces.mcp.guarding import keys_for
from wiki_api.surfaces.mcp.naming import (
    CLOSE_NAMES_TOOL,
    COMPARE_TOOL,
    MOVEMENT_TOOL,
    SORTS_TOOL,
    WRITTEN_TOOLS,
    Followed,
    followable,
)
from wiki_api.surfaces.mcp.projection import (
    MOST_EXAMPLES,
    Matches,
    Movement,
    Ranking,
    Related,
    Sorts,
    Thing,
    matches_of,
    sorts_of,
)

if TYPE_CHECKING:
    from collections.abc import Callable

SERVER_NAME: Final = "2009scape-wiki"
MOST_RESULT_CHARS: Final = 20_000

READ_ONLY: Final = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=False
)
BUDGET: Final = {"anthropic/maxResultSizeChars": MOST_RESULT_CHARS}

INSTRUCTIONS: Final = (
    "Answers questions about the 2009scape game world from a built snapshot of the "
    "game's own data. Every tool takes the name of something rather than a number, "
    "so pass what a player would say and let the tool work out which one is meant. "
    "If an answer comes back with an outcome other than found, read its note and the "
    "names it offers instead of guessing again. Answers arrive one page at a time "
    "and report how many there are in total, so ask for the next page only when the "
    "count says it is worth it. A name that answers to nothing may simply be "
    "misspelt; the closest real names can be looked up once the sort of thing is "
    "known, but which of them was meant is for whoever asked to say, never for you "
    "to decide.\n"
    "\n"
    "Every answer carries a `ref` such as `item:4587`. It is how you name one exact "
    "thing back to a tool, and it is the game's own bookkeeping: a person reading "
    "your answer has never seen one and cannot do anything with one. Never write a "
    "ref, a bare id, a map coordinate or a region number into what you say, and "
    "never set two things apart by their numbers. Tell them apart by what the wiki "
    "records about each instead, or ask which one was meant. If nothing in the "
    "answer distinguishes them, they are the same thing to whoever asked, so say "
    "how many there are and answer for all of them at once."
)

SEARCH_DESCRIPTION: Final = (
    "Find things in the game by words from their name. Use this when unsure what "
    "something is called or which one is meant; use the tool that fetches one thing "
    "once a name is known. Answers with a ranked set of names and identities."
)
GET_DESCRIPTION: Final = (
    "Fetch one thing in the game by name: what it is, the values worth knowing, and "
    "a count of everything it is joined to. The counts name the tool that reads "
    "each one, so this is the tool to call first and follow up from."
)
LIST_DESCRIPTION: Final = (
    "Go through everything of one sort in the game, a page at a time, in "
    "alphabetical order. Use this to survey what exists rather than to find one "
    "thing; searching by words is quicker when the name is roughly known."
)
ABOUT_DESCRIPTION: Final = (
    "Say which build of the game data is being answered from, and when it was made. "
    "Use this when an answer needs to be attributed, or looks out of date."
)
SORTS_DESCRIPTION: Final = (
    "List the sorts of thing this build knows about, with how many there are of "
    "each. Use this to settle what something is before asking about it by name, "
    "which the tool for close spellings needs told."
)
COMPARE_DESCRIPTION: Final = (
    "Go through one sort of thing by a number it records rather than by its name: "
    "everything above or below a threshold, ordered largest or smallest first. Use "
    "this for a question about how much or how many, and for how many things one "
    "name answers to, which the reply totals rather than making you fetch each. "
    "Say which number you mean in ordinary words; if none of them matches, the "
    "answer lists every number that sort of thing records, so ask again with one of "
    "those rather than guessing."
)
MOVEMENT_DESCRIPTION: Final = (
    "Say which way one thing's worth has gone over the record, and by how far. Use "
    "this for a question about a change over time rather than about what something "
    "is worth now, which the tool that fetches one thing already answers. The reply "
    "says how far to trust itself; an answer that says it was never really traded "
    "means what it says."
)
CLOSE_NAMES_DESCRIPTION: Final = (
    "Given a name that answered to nothing, offer the real names closest to it. Use "
    "this only after a lookup came back unknown, and only once whoever asked has "
    "said which sort of thing they meant. The answer is names and identities alone, "
    "on purpose: show it to whoever asked, let them say which one they meant, and "
    "look that one up. Never pick for them, and never treat an empty answer as "
    "permission to guess."
)

NameArg = Annotated[
    str,
    Field(
        description=(
            "What the thing is called, as a player would say it. An exact identity "
            "such as `item:4587` also works when one is already known."
        )
    ),
]
FollowedNameArg = Annotated[
    str, Field(description="What the thing to start from is called.")
]
FollowedOffsetArg = Annotated[int, Field(ge=0, description="How many answers to skip.")]
NarrowedTypeArg = Annotated[
    EntityType | None,
    Field(
        description=(
            "Keep only one sort of thing in the answer, and count only that sort. "
            "Leave out for all of them."
        )
    ),
]
WordsArg = Annotated[
    str, Field(description="Words from the name of whatever is being looked for.")
]
TypeArg = Annotated[
    EntityType | None,
    Field(description="Narrow the answer to one sort of thing, if it is known."),
]
OneTypeArg = Annotated[
    EntityType, Field(description="Which sort of thing to go through.")
]
MisspeltArg = Annotated[
    str,
    Field(description="The name that answered to nothing, exactly as it was given."),
]
NamedTypeArg = Annotated[
    EntityType,
    Field(
        description=(
            "Which sort of thing the name belongs to. There is no default: the same "
            "misspelling points at different things depending on the answer, so ask "
            "whoever wants to know before calling this."
        )
    ),
]
CloseLimitArg = Annotated[
    int,
    Field(
        ge=1,
        le=MOST_NEAR_LIMIT,
        description=(
            "At most how many close names to offer for a person to choose from."
        ),
    ),
]
CloseKeepArg = Annotated[
    float,
    Field(
        ge=0.0,
        le=1.0,
        description=(
            "How close to the best candidate a name has to be to be offered "
            "alongside it, as a share of the best score. Lower values offer more."
        ),
    ),
]
HoldsArg = Annotated[
    str | None,
    Field(
        description=(
            "Which recorded number to put the threshold against, in ordinary words. "
            "Leave out to sort without narrowing."
        )
    ),
]
HowArg = Annotated[
    Comparison,
    Field(description="How to measure what is recorded against the number given."),
]
NumberArg = Annotated[float, Field(description="The number to measure against.")]
OrderedByArg = Annotated[
    str | None,
    Field(
        description=(
            "Which recorded number to sort by, named the same way. Anything not "
            "recording it is left out rather than sorted last."
        )
    ),
]
DescendingArg = Annotated[
    bool, Field(description="Sort from the largest down rather than upwards.")
]
NamedArg = Annotated[
    str | None,
    Field(
        description=(
            "Keep only the ones called exactly this. Many things in the game share "
            "one name, so this answers how many of them there are and what each one "
            "records, in a single call rather than one per id."
        )
    ),
]
SinceArg = Annotated[
    str | None,
    Field(
        description=(
            "Read only from this day onwards, as `YYYY-MM-DD`. Leave out for the "
            "whole record."
        )
    ),
]
OffsetArg = Annotated[
    int,
    Field(
        ge=0,
        description=(
            "How many answers to skip. Pass back the `next_offset` from the previous "
            "answer to carry on from where it stopped."
        ),
    ),
]
LimitArg = Annotated[
    int,
    Field(
        ge=1,
        le=MAX_PAGE_SIZE,
        description="At most how many answers to send back at once.",
    ),
]


def create_server(
    settings: Settings | None = None, *, mounted: bool = False
) -> FastMCP:
    """Build the MCP server over the artifact the settings point at.

    `mounted` leaves out this server's own guard, because the application it hangs
    inside has already checked the caller.
    """
    chosen = settings if settings is not None else get_settings()
    provider = RepositoryProvider.open(chosen.artifact_path)
    server: FastMCP = FastMCP(
        name=SERVER_NAME,
        instructions=INSTRUCTIONS,
        auth=keys_for(chosen, mounted=mounted),
    )
    _offer_asking(server, provider, chosen)
    _offer_following(server, provider, chosen)
    return server


def main() -> None:
    """Run the server over whichever transport the settings ask for."""
    settings = get_settings()
    server = create_server(settings)
    if settings.mcp_transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


def _service(provider: RepositoryProvider, settings: Settings) -> KnowledgeService:
    return KnowledgeService(provider.current(), block_size=settings.mcp_rows)


def _day(written: str | None) -> date | None:
    """Read a day a caller wrote out, treating anything unreadable as no day at all."""
    if not written:
        return None
    try:
        return date.fromisoformat(written.strip())
    except ValueError:
        return None


def shape_of(answer: Callable[..., object]) -> str:
    """Name the shape a tool answers with, so the surface can state each one once."""
    return str(answer.__annotations__["return"])


def _offer_asking(
    server: FastMCP, provider: RepositoryProvider, settings: Settings
) -> None:
    def search(words: WordsArg, type: TypeArg = None, offset: OffsetArg = 0) -> Matches:
        service = _service(provider, settings)
        return matches_of(
            service.search(
                words,
                types=[type] if type is not None else None,
                limit=settings.mcp_rows,
                offset=offset,
            ),
            service.about().data_version,
        )

    def get_thing(name: NameArg, type: TypeArg = None) -> Answer[Thing]:
        service = _service(provider, settings)
        return about_thing(
            service.page_by_name(
                name,
                types=[type] if type is not None else None,
                limit=MOST_EXAMPLES,
            ),
            service.about().data_version,
        )

    def list_things(
        type: OneTypeArg, offset: OffsetArg = 0, limit: LimitArg = 20
    ) -> Matches:
        service = _service(provider, settings)
        return matches_of(
            service.list_type(type, limit=limit, offset=offset),
            service.about().data_version,
        )

    def about() -> Manifest:
        return _service(provider, settings).about()

    def list_sorts() -> Sorts:
        service = _service(provider, settings)
        described = service.describe_types()
        return sorts_of(
            described,
            {
                info.type: service.list_type(info.type, limit=1).total
                for info in described
            },
            service.about().data_version,
        )

    def compare_by_number(
        type: OneTypeArg,
        holds: HoldsArg = None,
        how: HowArg = Comparison.AT_LEAST,
        number: NumberArg = 0.0,
        ordered_by: OrderedByArg = None,
        descending: DescendingArg = False,
        named: NamedArg = None,
        offset: OffsetArg = 0,
    ) -> Answer[Ranking]:
        service = _service(provider, settings)
        return about_ranking(
            service.compare(
                type,
                holds=holds,
                how=how,
                number=number,
                ordered_by=ordered_by,
                descending=descending,
                named=named,
                limit=settings.mcp_rows,
                offset=offset,
            ),
            service.about().data_version,
        )

    def how_the_price_moved(name: NameArg, since: SinceArg = None) -> Answer[Movement]:
        service = _service(provider, settings)
        return about_movement(
            service.movement_by_name(name, since=_day(since)),
            service.about().data_version,
        )

    def find_close_names(
        name: MisspeltArg,
        type: NamedTypeArg,
        limit: CloseLimitArg = settings.near_limit,
        keep: CloseKeepArg = settings.near_keep,
    ) -> Matches:
        service = _service(provider, settings)
        return matches_of(
            service.near_names(
                name, type, limit=limit, keep=keep, floor=settings.near_floor
            ),
            service.about().data_version,
        )

    stated: set[str] = set()
    for name, description, answer, declares in (
        ("search", SEARCH_DESCRIPTION, search, True),
        ("get_thing", GET_DESCRIPTION, get_thing, True),
        ("list_things", LIST_DESCRIPTION, list_things, True),
        ("about", ABOUT_DESCRIPTION, about, True),
        (SORTS_TOOL, SORTS_DESCRIPTION, list_sorts, True),
        (COMPARE_TOOL, COMPARE_DESCRIPTION, compare_by_number, False),
        (MOVEMENT_TOOL, MOVEMENT_DESCRIPTION, how_the_price_moved, False),
        (CLOSE_NAMES_TOOL, CLOSE_NAMES_DESCRIPTION, find_close_names, True),
    ):
        server.tool(
            name=name,
            description=description,
            annotations=READ_ONLY,
            output_schema=... if declares and shape_of(answer) not in stated else None,
            meta=BUDGET,
        )(answer)
        stated.add(shape_of(answer))


def _offer_following(
    server: FastMCP, provider: RepositoryProvider, settings: Settings
) -> None:
    for followed in followable(_service(provider, settings).answerable()):
        server.tool(
            name=followed.name,
            description=followed.description,
            annotations=READ_ONLY,
            output_schema=None,
            meta=BUDGET,
        )(_following(provider, settings, followed))


def _following(
    provider: RepositoryProvider, settings: Settings, followed: Followed
) -> Callable[..., Answer[Related]]:
    """Build the tool that follows one link, taking a narrowing argument only where
    the link answers with more than one sort.
    """

    def walked(name: str, offset: int, sorts: EntityType | None) -> Answer[Related]:
        service = _service(provider, settings)
        return about_related(
            service.walk_by_name(
                name,
                followed.rel,
                followed.direction,
                types=followed.asked,
                sorts=None if sorts is None else [sorts],
                limit=settings.mcp_rows,
                offset=offset,
            ),
            service.about().data_version,
        )

    def follow(name: FollowedNameArg, offset: FollowedOffsetArg = 0) -> Answer[Related]:
        return walked(name, offset, None)

    def follow_one_sort(
        name: FollowedNameArg,
        type: NarrowedTypeArg = None,
        offset: FollowedOffsetArg = 0,
    ) -> Answer[Related]:
        return walked(name, offset, type)

    return follow_one_sort if followed.is_mixed else follow


if __name__ == "__main__":
    main()


# test cases


def test_the_written_tools_are_named_in_one_place_only() -> None:
    from wiki_api.domain.relationships import RELATIONSHIP_SPECS

    assert len(set(WRITTEN_TOOLS)) == len(WRITTEN_TOOLS)
    assert not set(WRITTEN_TOOLS) & {rel.value for rel in RELATIONSHIP_SPECS}


def test_a_link_this_build_cannot_follow_is_never_offered() -> None:
    from wiki_api.domain.relationships import RelationshipType

    held = frozenset({RelationshipType.DROPS})
    offered = {followed.rel for followed in followable(held)}
    assert offered == held
    assert len(followable(held)) == 2


def test_everything_this_surface_answers_is_read_only() -> None:
    assert READ_ONLY.readOnlyHint is True
    assert READ_ONLY.openWorldHint is False


def test_an_answer_declares_a_ceiling_a_reader_can_afford() -> None:
    assert BUDGET["anthropic/maxResultSizeChars"] == MOST_RESULT_CHARS
    assert MOST_RESULT_CHARS < 40_000


def test_a_shape_is_named_by_what_a_tool_answers_with() -> None:
    def answering_one() -> Matches:
        raise NotImplementedError

    def answering_another() -> Matches:
        raise NotImplementedError

    def answering_something_else() -> Sorts:
        raise NotImplementedError

    assert shape_of(answering_one) == shape_of(answering_another)
    assert shape_of(answering_one) != shape_of(answering_something_else)


def test_a_link_is_followed_from_a_name_said_in_fewer_words() -> None:
    for short, written in (
        (FollowedNameArg, NameArg),
        (FollowedOffsetArg, OffsetArg),
    ):
        assert len(_described(short)) < len(_described(written))
        assert _described(short)


def _described(annotated: object) -> str:
    from typing import get_args

    for piece in get_args(annotated):
        said = getattr(piece, "description", None)
        if isinstance(said, str):
            return said
    return ""


def test_a_thing_is_read_at_the_width_it_is_answered_with() -> None:
    import inspect

    body = inspect.getsource(_offer_asking)
    assert "limit=MOST_EXAMPLES" in body
    assert Settings().mcp_rows > MOST_EXAMPLES


def test_the_words_a_model_reads_first_explain_how_to_ask() -> None:
    assert "name" in INSTRUCTIONS
    assert "page" in INSTRUCTIONS


def test_every_written_tool_explains_when_to_reach_for_it() -> None:
    for described in (
        SEARCH_DESCRIPTION,
        GET_DESCRIPTION,
        LIST_DESCRIPTION,
        ABOUT_DESCRIPTION,
        SORTS_DESCRIPTION,
        CLOSE_NAMES_DESCRIPTION,
    ):
        assert "Use this" in described or "call first" in described


def test_no_two_written_tools_read_the_same() -> None:
    described_as = (
        SEARCH_DESCRIPTION,
        GET_DESCRIPTION,
        LIST_DESCRIPTION,
        ABOUT_DESCRIPTION,
        SORTS_DESCRIPTION,
        CLOSE_NAMES_DESCRIPTION,
    )
    assert len(set(described_as)) == len(described_as)


def test_the_tool_for_close_names_says_who_chooses_between_them() -> None:
    assert "Never pick for them" in CLOSE_NAMES_DESCRIPTION
    assert "whoever asked" in CLOSE_NAMES_DESCRIPTION


def test_the_words_read_first_say_that_a_misspelling_is_not_ours_to_settle() -> None:
    assert "never for you" in INSTRUCTIONS


def test_a_server_refuses_to_start_without_an_artifact() -> None:
    import pytest

    from wiki_api.repository.errors import ArtifactUnavailable

    settings = Settings(data_dir=Settings().data_dir / "nowhere")
    with pytest.raises(ArtifactUnavailable):
        create_server(settings)


def _ran(monkeypatch: object, transport: str) -> dict[str, object]:
    import pytest

    from wiki_api.surfaces.mcp import server as assembled

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started: dict[str, object] = {}

    def remember(_: object, **given: object) -> None:
        started.update(given)

    monkeypatch.setattr(assembled, "create_server", lambda _: None)
    monkeypatch.setattr(FastMCP, "run", remember, raising=False)
    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", transport)
    return started


def test_a_local_client_is_answered_over_the_transport_it_can_spawn(
    monkeypatch: object,
) -> None:
    from wiki_api.surfaces.mcp import server as assembled

    started = _ran(monkeypatch, "stdio")
    monkeypatch.setattr(  # type: ignore[attr-defined]
        assembled, "create_server", lambda _: FastMCP(name=SERVER_NAME)
    )
    main()
    assert started == {"transport": "stdio"}


def test_a_container_is_answered_somewhere_a_client_can_reach(
    monkeypatch: object,
) -> None:
    from wiki_api.surfaces.mcp import server as assembled

    started = _ran(monkeypatch, "http")
    monkeypatch.setattr(  # type: ignore[attr-defined]
        assembled, "create_server", lambda _: FastMCP(name=SERVER_NAME)
    )
    monkeypatch.setenv("WIKI_API_MCP_PORT", "9100")  # type: ignore[attr-defined]
    main()
    assert started["transport"] == "http"
    assert started["port"] == 9100


def test_the_words_read_first_say_a_ref_is_for_calling_with_not_for_saying() -> None:
    assert "Never write a ref" in INSTRUCTIONS
    assert "map coordinate" in INSTRUCTIONS


def test_the_words_read_first_say_what_to_do_with_things_nothing_tells_apart() -> None:
    assert "the same thing to whoever asked" in INSTRUCTIONS
