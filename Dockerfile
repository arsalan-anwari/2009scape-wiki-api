# Two stages: one that resolves the locked dependencies, one that runs them.
# The runtime image carries the virtualenv and the package, and no build tools.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# The lockfile alone first, so a change to the source does not reinstall the world.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --frozen --no-dev --no-editable --no-install-project

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm AS runtime

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WIKI_API_DATA_DIR=/data \
    WIKI_API_CONFIG_DIR=/config \
    WIKI_API_HTTP_HOST=0.0.0.0 \
    WIKI_API_HTTP_PORT=8000

RUN groupadd --system wiki \
 && useradd --system --gid wiki --home-dir /app --no-create-home wiki \
 && mkdir -p /data /config \
 && chown -R wiki:wiki /data /config

WORKDIR /app
COPY --from=build --chown=wiki:wiki /app/.venv /app/.venv

USER wiki
EXPOSE 8000
VOLUME ["/data", "/config"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('WIKI_API_HTTP_PORT', '8000') + '/health', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["scape2009-wiki-serve"]
