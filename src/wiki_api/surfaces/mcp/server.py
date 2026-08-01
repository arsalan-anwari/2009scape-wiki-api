"""Assembling the surface an agent talks to: four tools written out here, and one built
from the registry for every way a link can be followed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from wiki_api.config import Settings, get_settings
from wiki_api.core import KnowledgeService
from wiki_api.domain.identity import EntityType
from wiki_api.domain.manifest import Manifest
from wiki_api.domain.page import MAX_PAGE_SIZE
from wiki_api.repository.provider import RepositoryProvider
from wiki_api.surfaces.mcp.answers import Answer, about_related, about_thing
from wiki_api.surfaces.mcp.naming import Followed, followable
from wiki_api.surfaces.mcp.projection import Matches, Related, Thing, matches_of

if TYPE_CHECKING:
    from collections.abc import Callable

SERVER_NAME: Final = "2009scape-wiki"
MOST_RESULT_CHARS: Final = 20_000
WRITTEN_TOOLS: Final = ("search", "get_thing", "list_things", "about")

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
    "count says it is worth it."
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

NameArg = Annotated[
    str,
    Field(
        description=(
            "What the thing is called, as a player would say it. An exact identity "
            "such as `item:4587` also works when one is already known."
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


def create_server(settings: Settings | None = None) -> FastMCP:
    """A ready server, reading whatever artifact the settings point at."""
    chosen = settings if settings is not None else get_settings()
    provider = RepositoryProvider.open(chosen.artifact_path)
    server: FastMCP = FastMCP(name=SERVER_NAME, instructions=INSTRUCTIONS)
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


def _offer_asking(
    server: FastMCP, provider: RepositoryProvider, settings: Settings
) -> None:
    @server.tool(
        name="search",
        description=SEARCH_DESCRIPTION,
        annotations=READ_ONLY,
        meta=BUDGET,
    )
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

    @server.tool(
        name="get_thing",
        description=GET_DESCRIPTION,
        annotations=READ_ONLY,
        meta=BUDGET,
    )
    def get_thing(name: NameArg, type: TypeArg = None) -> Answer[Thing]:
        service = _service(provider, settings)
        return about_thing(
            service.page_by_name(
                name,
                types=[type] if type is not None else None,
                limit=settings.mcp_rows,
            ),
            service.about().data_version,
        )

    @server.tool(
        name="list_things",
        description=LIST_DESCRIPTION,
        annotations=READ_ONLY,
        meta=BUDGET,
    )
    def list_things(
        type: OneTypeArg, offset: OffsetArg = 0, limit: LimitArg = 20
    ) -> Matches:
        service = _service(provider, settings)
        return matches_of(
            service.list_type(type, limit=limit, offset=offset),
            service.about().data_version,
        )

    @server.tool(
        name="about",
        description=ABOUT_DESCRIPTION,
        annotations=READ_ONLY,
        meta=BUDGET,
    )
    def about() -> Manifest:
        return _service(provider, settings).about()


def _offer_following(
    server: FastMCP, provider: RepositoryProvider, settings: Settings
) -> None:
    for followed in followable():
        server.tool(
            name=followed.name,
            description=followed.description,
            annotations=READ_ONLY,
            meta=BUDGET,
        )(_following(provider, settings, followed))


def _following(
    provider: RepositoryProvider, settings: Settings, followed: Followed
) -> Callable[[str, int], Answer[Related]]:
    def follow(name: NameArg, offset: OffsetArg = 0) -> Answer[Related]:
        service = _service(provider, settings)
        return about_related(
            service.walk_by_name(
                name,
                followed.rel,
                followed.direction,
                types=followed.asked,
                limit=settings.mcp_rows,
                offset=offset,
            ),
            service.about().data_version,
        )

    return follow


# test cases


def test_the_tools_offered_are_the_ones_the_registry_implies() -> None:
    from wiki_api.surfaces.mcp.naming import followable as declared

    generated = {followed.name for followed in declared()}
    assert not set(WRITTEN_TOOLS) & generated


def test_the_written_tools_are_named_in_one_place_only() -> None:
    from wiki_api.domain.relationships import RELATIONSHIP_SPECS

    assert len(set(WRITTEN_TOOLS)) == len(WRITTEN_TOOLS)
    assert not set(WRITTEN_TOOLS) & {rel.value for rel in RELATIONSHIP_SPECS}


def test_everything_this_surface_answers_is_read_only() -> None:
    assert READ_ONLY.readOnlyHint is True
    assert READ_ONLY.openWorldHint is False


def test_an_answer_declares_a_ceiling_a_reader_can_afford() -> None:
    assert BUDGET["anthropic/maxResultSizeChars"] == MOST_RESULT_CHARS
    assert MOST_RESULT_CHARS < 40_000


def test_the_words_a_model_reads_first_explain_how_to_ask() -> None:
    assert "name" in INSTRUCTIONS
    assert "page" in INSTRUCTIONS


def test_every_written_tool_explains_when_to_reach_for_it() -> None:
    for described in (
        SEARCH_DESCRIPTION,
        GET_DESCRIPTION,
        LIST_DESCRIPTION,
        ABOUT_DESCRIPTION,
    ):
        assert "Use this" in described or "call first" in described


def test_no_two_written_tools_read_the_same() -> None:
    described_as = (
        SEARCH_DESCRIPTION,
        GET_DESCRIPTION,
        LIST_DESCRIPTION,
        ABOUT_DESCRIPTION,
    )
    assert len(set(described_as)) == len(described_as)


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
