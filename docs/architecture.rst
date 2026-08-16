Architecture
============

Two halves that never meet. One is an offline build turning game sources into a file.
The other serves that file. They share only the domain model, and an import contract
stops the serving half from importing the build.

.. code-block:: text

     game repositories        overlays          identity
             |                   |                 |
             +---------+---------+-----------------+
                       |
                pipeline: staging, adapters, merge, writer
                       |
                       v
              knowledge.sqlite3   one immutable build, FTS5 included
                       |
    ===================|=====================================  offline above
                       v                                        serving below
                  repository   one read protocol, SQLite or in memory
                       |
                     core      resolve, walk, search, compare, prices
                       |
          +------------+------------+
          |                         |
    surfaces/http             surfaces/mcp
    FastAPI at /v1            FastMCP tools
          |                         |
          +------------+------------+
                       |
                   guarding   tokens, per caller share, bans

     domain: entities, relationships, attribute registry, read by all of them

Layers
------

``domain``
    The knowledge model and nothing else. Imports no transport, storage or ingestion
    library, so the same model serves the offline build and a running server.

``repository``
    One read protocol, ``KnowledgeRepository``, and two implementations: SQLite over the
    built artifact with FTS5, and in memory for tests and small tools.

``core``
    The query logic both surfaces share. Resolve, walk, search, compare, price history,
    and describing a page as data. It answers found, moved, hidden or missing rather
    than raising.

``surfaces``
    Two ways of asking the core the same questions. Neither holds query logic; they
    shape what the core hands back.

``access``
    Issuing keys, checking tokens, per caller shares, shut-out addresses. A leaf: it
    knows nothing about the game or how it is served.

``pipeline``
    The offline build. See :doc:`pipeline`.

``config`` and ``serve``
    One settings model, and the entry point deciding which surfaces this process runs.

What holds them apart
---------------------

Six import contracts are declared in ``pyproject.toml`` and checked by import-linter as
part of ``poe check``.

1. ``surfaces`` may import ``core``, then ``repository``, then ``domain``. Never back.
2. Runtime never imports the offline pipeline.
3. ``core`` and ``surfaces`` cannot import a concrete repository, only the protocol.
4. ``access`` imports nothing else in the project, not even ``config``.
5. Nothing that serves requests can import ``access.issuing`` or ``access.cli``.
6. ``domain`` cannot import fastapi, fastmcp, starlette, sqlite3, httpx or lxml.

``uv run poe imports`` is the fastest way to find out whether a new module belongs where
you put it.

Two properties
--------------

**A build is immutable.** The artifact is opened read only. Every response repeats which
build answered it, and a pinned answer can be cached forever.

**A build can be replaced without stopping.** ``repository.provider`` holds what a
surface is reading; swapping it hands the old one back rather than closing it, because
requests in flight are still reading from it.

Reading the code
----------------

Most modules carry a one-line docstring saying what they are for, and test cases live in
the same file as the code they cover, below a ``# test cases`` marker. Integration
tests, which cross module boundaries, live in ``tests/integration``.
