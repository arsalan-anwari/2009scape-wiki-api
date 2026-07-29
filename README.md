> This project is a WIP, please wait for official release

# 2009scape-wiki-api

A backend service that turns the 2009scape game data into a clean, searchable
knowledge base. It reads the raw game sources (items, NPCs, shops, drop tables,
quests and more), cleans them into a uniform format, and serves them over two
interfaces:

- an HTTP JSON API, meant to be used by a separate wiki website
- an MCP server, so AI agents like Claude can answer questions about the game

## How it works

1. Read the raw game sources.
2. Clean them into entities (items, NPCs, quests, shops, locations) and the
   relationships between them (dropped by, sold in, rewarded by).
3. Store the result as a build artifact (a SQLite database).
4. Serve it through the HTTP API and the MCP server.

The database is always rebuilt from source and never edited by hand. The cleaned
dataset is published to Hugging Face and downloaded at runtime, so it is not
committed to this repo.

## Project layout

- src/wiki_api: the installable package
  - domain: the core data model (entities and relationships)
  - repository: data access behind one interface (SQLite/FTS5 and in-memory)
  - core: the query logic shared by both interfaces
  - surfaces/http: the FastAPI HTTP API
  - surfaces/mcp: the MCP server
  - pipeline/artifact: the offline code that builds the dataset
- tests: integration tests and the hand-made knowledge fixtures
- scripts: helper scripts for development and publishing
- docs: public API documentation

## The knowledge model

Everything the API serves is an **entity**: an item, NPC, shop or quest with
one identity, one shape, and typed **relationships** to other entities.

- Identity is `(type, id)` and never changes. Numeric ids overlap between types,
  so an id alone is never an identity.
- Each entity also has a readable `slug`, unique within its type. Retired slugs
  and community shorthand live on as **aliases** that redirect, so links do not
  rot.
- Duplicate ids for the same thing (noted, bound or placeholder items) point at a
  canonical entity and stay out of search and index listings.
- Type-specific values (buy limit, lifepoints, quest length) are declared once in
  an **attribute registry** that carries their label, group and units, so pages
  and API payloads can be rendered without any code knowing the field names.
- Relationships carry their own data meaning a drop keeps its weight *and* its
  denominator, so a rate renders exactly (ex: `1/128`).
- Every fact records where it came from and which game version it reflects.

## Development

Requires uv, which installs and manages the pinned Python version for you.

```
uv sync --all-extras       // install all dependencies
uv run poe check           // run linting, type checks, boundary checks and tests
uv run poe fix             // auto fix formatting and simple lint issues
scripts/test_ci.sh --fix --no-act   // fix, run the checks, ignore CI workflow
scripts/test_ci.sh --fix   // fix, run the checks, then run the CI workflow locally
```
