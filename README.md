# 2009scape-wiki-api

[![PyPI](https://img.shields.io/pypi/v/scape2009-wiki-api?logo=pypi&logoColor=white)](https://pypi.org/project/scape2009-wiki-api/)
[![Downloads](https://img.shields.io/pypi/dm/scape2009-wiki-api?logo=pypi&logoColor=white&label=downloads)](https://pypistats.org/packages/scape2009-wiki-api)
[![Python](https://img.shields.io/pypi/pyversions/scape2009-wiki-api?logo=python&logoColor=white)](https://pypi.org/project/scape2009-wiki-api/)
[![Docker](https://img.shields.io/docker/v/arsalananwari/2009scape-wiki-api?logo=docker&logoColor=white&label=docker)](https://hub.docker.com/r/arsalananwari/2009scape-wiki-api)
[![Image size](https://img.shields.io/docker/image-size/arsalananwari/2009scape-wiki-api/latest?logo=docker&logoColor=white&label=image)](https://hub.docker.com/r/arsalananwari/2009scape-wiki-api)
[![CI](https://github.com/arsalan-anwari/2009scape-wiki-api/actions/workflows/ci.yml/badge.svg)](https://github.com/arsalan-anwari/2009scape-wiki-api/actions/workflows/ci.yml)

[![deb](https://img.shields.io/badge/deb-amd64-A80030?logo=debian&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![rpm](https://img.shields.io/badge/rpm-x86__64-294172?logo=fedora&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![Arch](https://img.shields.io/badge/pkg.tar.zst-x86__64-1793D1?logo=archlinux&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![Dataset](https://img.shields.io/badge/dataset-Hugging%20Face-FFD21E?logo=huggingface&logoColor=black)](https://huggingface.co/datasets/arsalan-anwari/2009scape-wiki-api-data)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-222222?logo=github&logoColor=white)](https://arsalan-anwari.github.io/2009scape-wiki-api/)
[![FAST API docs](https://img.shields.io/badge/docs-OpenAPI-6BA539?logo=openapiinitiative&logoColor=white)](docs/http-api.rst)
[![MCP](https://img.shields.io/badge/MCP-server-000000?logo=modelcontextprotocol&logoColor=white)](docs/mcp.rst)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Turns the raw 2009scape game sources (items, NPCs, shops, drop tables, quests, locations)
into one immutable SQLite artifact, served two ways: a **FastAPI** contract for a wiki
front end, and an **MCP server** for Claude and other agents.

```mermaid
flowchart LR
    SRC["game sources<br/>+ overlays"] --> PIPE["pipeline/artifact<br/>offline build"]
    PIPE --> ART[("knowledge.sqlite3<br/>one immutable build")]
    subgraph RUN ["one image, one process, one port"]
        REPO["repository<br/>SQLite + FTS5"] --> CORE["core<br/>resolve, walk, search"]
        CORE --> HTTP["surfaces/http<br/>FastAPI"]
        CORE --> MCP["surfaces/mcp<br/>FastMCP"]
        HTTP --> GUARD["guarding<br/>token, rate, bans"]
        MCP --> GUARD
    end
    ART --> REPO
    GUARD --> WIKI["wiki front end"]
    GUARD --> AGENT["Claude, editors,<br/>any MCP client"]
    DOM["domain<br/>entities, relationships<br/>attribute registry"] -.-> PIPE & REPO & CORE
```

A build holds ~20,000 entities, ~83,000 relationships and two years of weekly Grand
Exchange prices. It ships on
[Hugging Face](https://huggingface.co/datasets/arsalan-anwari/2009scape-wiki-api-data),
never in this repository.

## Installing

```bash
uv tool install scape2009-wiki-api                        # a Python environment
docker run -p 8000:8000 arsalananwari/2009scape-wiki-api  # a container
```

Debian, Fedora and Arch packages are on the
[releases page](https://github.com/arsalan-anwari/2009scape-wiki-api/releases); they carry
the dataset, so an offline machine answers everything. See [install](docs/install.rst).

## Getting started

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
uv run poe download-data          # the published dataset into data/
uv run poe keys init              # the key this deployment answers, once
uv run poe keys issue --label me  # one token, saved under tokens/me.json
uv run poe serve                  # HTTP on :8000, contract at /docs

TOKEN=$(jq -r .access_token ~/.config/scape2009-wiki-api/tokens/me.json)
curl -H "authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/entities/item/dragon-scimitar
```

Both surfaces refuse to start without a dataset and an issuer key, naming which is
missing. `WIKI_API_AUTH_MODE=off` answers everyone instead.

This repository carries a `.mcp.json`, so running `claude` here offers the MCP server.

## Documentation

`uv run poe docs` builds the full documentation into `docs/out`, or read the sources:

| read | for |
| --- | --- |
| [install](docs/install.rst), [getting started](docs/getting-started.rst) | packages, containers, first questions |
| [configuration](docs/configuration.rst), [access](docs/access.rst) | settings, `deploy.json`, keys, tokens, bans |
| [http-api](docs/http-api.rst), [mcp](docs/mcp.rst), [demos](docs/demos.rst) | the two surfaces, and worked examples |
| [architecture](docs/architecture.rst), [data model](docs/data-model.rst), [pipeline](docs/pipeline.rst) | layers, entities, how a build is made |
| [extending](docs/extending.rst), [contributing](docs/contributing.rst) | adding a sort, a relationship, a release |

Versions are decided in [`CHANGELOG.md`](CHANGELOG.md) alone; see
[contributing](docs/contributing.rst) for how a release is cut.
