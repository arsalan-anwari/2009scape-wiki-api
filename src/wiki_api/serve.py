"""Start whichever surfaces a deployment asks for.

The one module allowed to know both surfaces exist. Serving both mounts the tools
inside the HTTP application, so there is one port, one health check and one guard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import uvicorn

from wiki_api.config import Settings, get_settings
from wiki_api.surfaces.http.app import Mounted, WikiApi, create_app
from wiki_api.surfaces.mcp.server import create_server

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import FastMCP

TOOLS_PATH: Final = "/mcp"
WORKERS: Final = 1


def create_combined(settings: Settings | None = None) -> WikiApi:
    """Build the HTTP application with the tools mounted underneath it."""
    chosen = settings if settings is not None else get_settings()
    server: FastMCP = create_server(chosen, mounted=True)
    return create_app(
        chosen, mount=Mounted(path=TOOLS_PATH, app=server.http_app(path="/"))
    )


def main() -> None:
    """Serve whatever this deployment is configured to serve."""
    settings = get_settings()
    if settings.surfaces == "mcp":
        _tools(settings)
        return
    combined = settings.surfaces == "both"
    _served(create_combined(settings) if combined else create_app(settings), settings)


def _tools(settings: Settings) -> None:
    server = create_server(settings)
    if settings.mcp_transport == "stdio":
        server.run(transport="stdio")
        return
    server.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


def _served(app: WikiApi, settings: Settings) -> None:
    """Run one application on one worker.

    One worker only: the tools hold a session per client in this process, so a second
    would answer half a client's requests from a process that never saw it.
    """
    uvicorn.run(app, host=settings.http_host, port=settings.http_port, workers=WORKERS)


if __name__ == "__main__":
    main()


# test cases


def _over(artifact: Path) -> Settings:
    """Settings answering from the artifact this run built.

    Named rather than left to default, because the tools open the artifact as they are
    built, and a machine that has never downloaded one still has to serve them.
    """
    return Settings(data_dir=artifact.parent, artifact_filename=artifact.name)


def test_serving_both_hangs_the_tools_off_the_contract(fixture_artifact: Path) -> None:
    app = create_combined(_over(fixture_artifact))
    mounted = [
        route for route in app.routes if str(getattr(route, "path", "")) == TOOLS_PATH
    ]
    assert mounted


def test_serving_both_keeps_the_contract_where_it_was(fixture_artifact: Path) -> None:
    published = set(create_combined(_over(fixture_artifact)).openapi()["paths"])
    assert "/health" in published
    assert "/v1/entities/{entity_type}/{ref}" in published


def test_the_tools_are_never_published_as_part_of_the_contract(
    fixture_artifact: Path,
) -> None:
    published = set(create_combined(_over(fixture_artifact)).openapi()["paths"])
    assert not any(path.startswith(TOOLS_PATH) for path in published)


def _ran(monkeypatch: object, surfaces: str) -> dict[str, object]:
    import pytest
    import uvicorn as serving

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started: dict[str, object] = {}

    def remember(app: object, **given: object) -> None:
        started["app"] = app
        started.update(given)

    monkeypatch.setattr(serving, "run", remember)
    monkeypatch.setenv("WIKI_API_SURFACES", surfaces)
    return started


def test_the_contract_alone_is_served_on_its_own_port(monkeypatch: object) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started = _ran(monkeypatch, "http")
    monkeypatch.setenv("WIKI_API_HTTP_PORT", "9001")
    main()
    assert isinstance(started["app"], WikiApi)
    assert started["port"] == 9001


def test_both_surfaces_are_served_from_one_process(
    monkeypatch: object, fixture_artifact: Path
) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started = _ran(monkeypatch, "both")
    monkeypatch.setenv("WIKI_API_DATA_DIR", str(fixture_artifact.parent))
    monkeypatch.setenv("WIKI_API_ARTIFACT_FILENAME", fixture_artifact.name)
    main()
    app = started["app"]
    assert isinstance(app, WikiApi)
    assert any(str(getattr(route, "path", "")) == TOOLS_PATH for route in app.routes)
    assert started["workers"] == WORKERS


def test_the_tools_alone_are_served_by_their_own_server(monkeypatch: object) -> None:
    import pytest
    from fastmcp import FastMCP as Server

    from wiki_api import serve as serving

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started: dict[str, object] = {}

    def remember(_: object, **given: object) -> None:
        started.update(given)

    monkeypatch.setattr(Server, "run", remember, raising=False)
    monkeypatch.setattr(serving, "create_server", lambda _: Server(name="x"))
    monkeypatch.setenv("WIKI_API_SURFACES", "mcp")
    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", "stdio")
    main()
    assert started == {"transport": "stdio"}


def test_the_tools_alone_can_be_reached_over_a_network(monkeypatch: object) -> None:
    import pytest
    from fastmcp import FastMCP as Server

    from wiki_api import serve as serving

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    started: dict[str, object] = {}

    def remember(_: object, **given: object) -> None:
        started.update(given)

    monkeypatch.setattr(Server, "run", remember, raising=False)
    monkeypatch.setattr(serving, "create_server", lambda _: Server(name="x"))
    monkeypatch.setenv("WIKI_API_SURFACES", "mcp")
    monkeypatch.setenv("WIKI_API_MCP_TRANSPORT", "http")
    monkeypatch.setenv("WIKI_API_MCP_PORT", "9100")
    main()
    assert started["transport"] == "http"
    assert started["port"] == 9100


def test_serving_more_than_one_worker_is_never_asked_for() -> None:
    assert WORKERS == 1
