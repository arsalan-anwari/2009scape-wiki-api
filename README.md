# 2009scape-wiki-api

A backend service that turns the 2009scape game data into a clean, searchable
knowledge base. It reads the raw game sources (items, NPCs, shops, drop tables,
quests and more), cleans them into a uniform format, and serves them over two
interfaces:

- an HTTP JSON API, meant to be used by a separate wiki website
- an MCP server, so AI agents like Claude can answer questions about the game

## How it works

This is a data pipeline, not a hand-edited wiki. The flow is:

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
  - repository: data access behind one interface
  - core: the query logic shared by both interfaces
  - surfaces/http: the FastAPI HTTP API
  - surfaces/mcp: the MCP server
  - pipeline: the offline code that builds the dataset
- tests: integration tests
- scripts: helper scripts for development and publishing
- docs: public API documentation

## Development

Requires uv, which installs and manages the pinned Python version for you.

```
uv sync --all-extras       // install all dependencies
uv run poe check           // run linting, type checks, boundary checks and tests
uv run poe fix             // auto fix formatting and simple lint issues
scripts/test_ci.sh --fix   // fix, run the checks, then run the CI workflow locally
```
