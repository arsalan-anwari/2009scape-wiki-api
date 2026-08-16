# Changelog

Every released version, newest first, in the format
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) writes down, versioned by
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The top heading carrying a version number is the version being released.
`scripts/release.sh` reads it from here and writes it into every file that names one, so
this file is the only place a version is decided.

## [1.1.0] - 2026-08-16

Every way of installing this is now complete on its own.

### Added

- **`data` command.** `scape2009-wiki-data pull` fetches the published dataset into the
  directory this deployment serves from.
- **One dispatcher behind every install.** `scape2009-wiki-api <serve|mcp|keys|data>`,
  which is what the container and the frozen build already were internally. 

### Changed

- **`data_dir` defaults to `~/.local/share/scape2009-wiki-api`**, honouring
  `XDG_DATA_HOME`, rather than a `data` directory relative to the working directory. 
- **The tools over stdio no longer need a key to start.** Nothing checks one over
  stdio.
- **Improved sphinx docs** by making them shorter and more structured.

### Fixed

- A deployment that cannot start now says so in one line naming what is missing.
- `serve` finds a missing dataset before starting a server rather than during ASGI
  startup.
- A dataset can be fetched before an issuer key exists. 
- README links are absolute, so the one file reads correctly on both GitHub and PyPI.

[1.1.0]: https://github.com/arsalan-anwari/2009scape-wiki-api/releases/tag/v1.1.0

## [1.0.0] - 2026-08-16

The first release. The pipeline, both surfaces, the guard and four ways of installing it.

### Added

- **Offline build.** `pipeline/` stages the game's own repositories and its cache,
  merges hand-written overlays over them, and writes one immutable SQLite artifact.
  Same inputs, same bytes.
- **Knowledge model.** Six entity types (item, npc, shop, quest, scenery, location) and
  nine relationships between them, with a declared attribute registry, collapsed
  variants, stable `(type, id)` identity and derived slugs.
- **Query core.** One surface-agnostic layer answering resolve, walk, search and
  compare, returning found, moved, hidden or missing rather than raising.
- **HTTP contract.** A versioned FastAPI surface at `/v1` returning render-ready JSON
  and page descriptors, with `ETag`, `X-Data-Version` and a published OpenAPI document.
- **MCP surface.** A FastMCP server whose tools are generated from the relationship
  registry, so every way of following a link is a question a model can ask by name.
- **Guard.** Ed25519 bearer tokens checked against an issuer public key, a per-caller
  share, and shut-out addresses that outlive a restart. Minting is unreachable from
  anything that serves.
- **One process, one port.** Serving both surfaces mounts the tools inside the HTTP
  application, behind the same guard and one health check.
- **Grand Exchange history.** Two years of weekly price snapshots, queryable per item.
- **Container.** An image carrying the dataset, so a deployment with no network can
  serve it. Published to Docker Hub as `arsalananwari/2009scape-wiki-api`.
- **System packages.** A standalone binary wrapped in a `.deb`, an `.rpm` and an Arch
  package, for installing it on Linux without Python.
- **PyPI.** Published as `scape2009-wiki-api`, with `scape2009-wiki-serve`,
  `scape2009-wiki-mcp` and `scape2009-wiki-keys` as console scripts.
  `scape2009-wiki-data` joined them in 1.1.0.
- **Sphinx Docs.** Added sphinx docs and release pipeline to github pages. 

[1.0.0]: https://github.com/arsalan-anwari/2009scape-wiki-api/releases/tag/v1.0.0
