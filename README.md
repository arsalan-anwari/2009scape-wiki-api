# 2009scape-wiki-api

[![PyPI](https://img.shields.io/pypi/v/scape2009-wiki-api?logo=pypi&logoColor=white)](https://pypi.org/project/scape2009-wiki-api/)
[![PyPi Downloads](https://img.shields.io/pypi/dm/scape2009-wiki-api?logo=pypi&logoColor=white&label=downloads)](https://pypistats.org/packages/scape2009-wiki-api)
![Docker Pulls](https://img.shields.io/docker/pulls/arsalananwari/2009scape-wiki-api)
![GitHub all releases](https://img.shields.io/github/downloads/arsalan-anwari/2009scape-wiki-api/total)
[![Docker](https://img.shields.io/docker/v/arsalananwari/2009scape-wiki-api?logo=docker&logoColor=white&label=docker)](https://hub.docker.com/r/arsalananwari/2009scape-wiki-api)
[![Image size](https://img.shields.io/docker/image-size/arsalananwari/2009scape-wiki-api/latest?logo=docker&logoColor=white&label=image)](https://hub.docker.com/r/arsalananwari/2009scape-wiki-api)
[![CI](https://github.com/arsalan-anwari/2009scape-wiki-api/actions/workflows/ci.yml/badge.svg)](https://github.com/arsalan-anwari/2009scape-wiki-api/actions/workflows/ci.yml)

[![deb](https://img.shields.io/badge/deb-amd64-A80030?logo=debian&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![rpm](https://img.shields.io/badge/rpm-x86__64-294172?logo=fedora&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![Arch](https://img.shields.io/badge/pkg.tar.zst-x86__64-1793D1?logo=archlinux&logoColor=white)](https://github.com/arsalan-anwari/2009scape-wiki-api/releases/latest)
[![Dataset](https://img.shields.io/badge/dataset-Hugging%20Face-FFD21E?logo=huggingface&logoColor=black)](https://huggingface.co/datasets/arsalan-anwari/2009scape-wiki-api-data)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-222222?logo=github&logoColor=white)](https://arsalan-anwari.github.io/2009scape-wiki-api/)
[![FAST API docs](https://img.shields.io/badge/docs-OpenAPI-6BA539?logo=openapiinitiative&logoColor=white)](https://arsalan-anwari.github.io/2009scape-wiki-api/http-api.html)
[![MCP](https://img.shields.io/badge/MCP-server-000000?logo=modelcontextprotocol&logoColor=white)](https://arsalan-anwari.github.io/2009scape-wiki-api/mcp.html)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/arsalan-anwari/2009scape-wiki-api/blob/main/LICENSE)

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

Debian, Fedora and Arch packages are on the
[releases page](https://github.com/arsalan-anwari/2009scape-wiki-api/releases). Each way
in is complete on its own: dataset, settings file, keys and the commands to manage them.

See [install](https://arsalan-anwari.github.io/2009scape-wiki-api/install.html). For 
install guide per method

## Documentation

The full documentation is at
[arsalan-anwari.github.io/2009scape-wiki-api](https://arsalan-anwari.github.io/2009scape-wiki-api/).

| read | for |
| --- | --- |
| [install](https://arsalan-anwari.github.io/2009scape-wiki-api/install.html), [deployment](https://arsalan-anwari.github.io/2009scape-wiki-api/deployment.html) | packages, containers, first questions |
| [configuration](https://arsalan-anwari.github.io/2009scape-wiki-api/configuration.html), [access](https://arsalan-anwari.github.io/2009scape-wiki-api/access.html) | settings, `deploy.json`, keys, tokens, bans |
| [http-api](https://arsalan-anwari.github.io/2009scape-wiki-api/http-api.html), [mcp](https://arsalan-anwari.github.io/2009scape-wiki-api/mcp.html), [demos](https://arsalan-anwari.github.io/2009scape-wiki-api/demos.html) | the two surfaces, and worked examples |
| [architecture](https://arsalan-anwari.github.io/2009scape-wiki-api/architecture.html), [data model](https://arsalan-anwari.github.io/2009scape-wiki-api/data-model.html), [pipeline](https://arsalan-anwari.github.io/2009scape-wiki-api/pipeline.html) | layers, entities, how a build is made |
| [extending](https://arsalan-anwari.github.io/2009scape-wiki-api/extending.html), [contributing](https://arsalan-anwari.github.io/2009scape-wiki-api/contributing.html) | adding a sort, a relationship, a release |

