"""Assembling the surface: open the artifact, wire the routes, fail loudly if not.

Startup opens the artifact and keeps it in a holder the routes read per request. A
process that cannot open one refuses to start, because this service has nothing useful
to answer without data and a healthy looking process that 503s every request is harder
to diagnose than one that never came up.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from wiki_api.config import Settings, get_settings
from wiki_api.repository.provider import RepositoryProvider
from wiki_api.surfaces.http import errors, openapi
from wiki_api.surfaces.http.caching import DATA_VERSION_HEADER, Validators
from wiki_api.surfaces.http.dependencies import PROVIDER_STATE, SETTINGS_STATE
from wiki_api.surfaces.http.routes import (
    discovery_router,
    entities_router,
    meta_router,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

COMPRESS_FROM = 1024
READ_ONLY_METHODS = ["GET", "HEAD", "OPTIONS"]
EXPOSED_HEADERS = ["etag", "last-modified", DATA_VERSION_HEADER]


class WikiApi(FastAPI):
    """An application whose published description is the shaped one."""

    def openapi(self) -> dict[str, Any]:
        if not self.openapi_schema:
            self.openapi_schema = openapi.build(self)
        return self.openapi_schema


def create_app(settings: Settings | None = None) -> WikiApi:
    """A ready application, reading whatever artifact the settings point at."""
    chosen = settings if settings is not None else get_settings()
    app = WikiApi(
        title=openapi.TITLE,
        version=openapi.VERSION,
        description=openapi.DESCRIPTION,
        openapi_tags=openapi.TAGS,
        lifespan=_lifespan,
        generate_unique_id_function=openapi.operation_id,
        middleware=_middleware(chosen),
    )
    setattr(app.state, SETTINGS_STATE, chosen)
    errors.install(app)
    app.include_router(meta_router)
    app.include_router(entities_router)
    app.include_router(discovery_router)
    return app


def _middleware(settings: Settings) -> list[Middleware]:
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=READ_ONLY_METHODS,
            allow_headers=["*"],
            expose_headers=EXPOSED_HEADERS,
        ),
        Middleware(GZipMiddleware, minimum_size=COMPRESS_FROM),
        Middleware(Validators, settings=settings),
    ]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = getattr(app.state, SETTINGS_STATE)
    provider = RepositoryProvider.open(settings.artifact_path)
    setattr(app.state, PROVIDER_STATE, provider)
    try:
        yield
    finally:
        provider.close()


# test cases


def test_an_application_serves_every_part_of_the_contract() -> None:
    published = set(create_app().openapi()["paths"])
    assert "/health" in published
    assert "/v1/about" in published
    assert "/v1/search" in published
    assert "/v1/entities/{entity_type}/{ref}" in published


def test_a_browser_can_read_the_headers_it_needs_to_cache_with() -> None:
    assert DATA_VERSION_HEADER in EXPOSED_HEADERS
    assert "etag" in EXPOSED_HEADERS


def test_nothing_but_reading_is_allowed_across_an_origin() -> None:
    assert "POST" not in READ_ONLY_METHODS
    assert "DELETE" not in READ_ONLY_METHODS


def test_the_settings_travel_with_the_application_rather_than_a_global() -> None:
    settings = Settings(artifact_filename="elsewhere.sqlite3")
    app = create_app(settings)
    assert getattr(app.state, SETTINGS_STATE) is settings


def test_the_published_schema_is_the_shaped_one() -> None:
    document = create_app().openapi()
    assert document["info"]["title"] == openapi.TITLE
    assert "enum" not in document["components"]["schemas"]["EntityType"]


def test_the_schema_is_built_once_and_then_held() -> None:
    app = create_app()
    assert app.openapi() is app.openapi()
