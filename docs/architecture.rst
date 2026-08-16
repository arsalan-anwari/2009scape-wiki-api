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

=======================  ==========================================================
``domain``               The knowledge model and nothing else. No transport,
                         storage or ingestion library, so the same model serves
                         the offline build and a running server.
``repository``           One read protocol, ``KnowledgeRepository``, two
                         implementations: SQLite with FTS5, and in memory.
``core``                 The query logic both surfaces share: resolve, walk,
                         search, compare, prices, describing a page as data. It
                         answers found, moved, hidden or missing, never raises.
``surfaces``             Two ways of asking the core the same questions. They
                         shape answers; they hold no query logic.
``access``               Issuing keys, checking tokens, caller shares, bans. A
                         leaf: knows nothing about the game or how it is served.
``pipeline``             The offline build. See :doc:`pipeline`.
``config``, ``serve``    One settings model, and which surfaces this process runs.
``cli``, ``dataset``     The four commands, and fetching a published build.
                         Nothing that serves may import either, so a surface a
                         client spawned cannot reach the network on its way up.
=======================  ==========================================================

What holds them apart
---------------------

1. ``surfaces`` may import ``core``, then ``repository``, then ``domain``. Never back.
2. Runtime never imports the offline pipeline.
3. ``core`` and ``surfaces`` cannot import a concrete repository, only the protocol.
4. ``access`` imports nothing else in the project, not even ``config``.
5. Nothing that serves requests can import ``access.issuing`` or ``access.cli``.
6. Nothing that serves requests can import ``dataset``.
7. ``domain`` cannot import fastapi, fastmcp, starlette, sqlite3, httpx or lxml.


Three properties
----------------

**A build is immutable.** The artifact is opened read only. Every response repeats which
build answered it, and a pinned answer can be cached forever.

**A build can be replaced without stopping.** ``repository.provider`` holds what a
surface reads; swapping it hands the old one back rather than closing it, because
requests in flight still read from it. 

**A process serving both runs one worker.** The tools keep a session per client in
memory, so a second worker would answer half a client's requests from a process that
never saw it. Rate shares are counted per process for the same reason, so two replicas
mean two shares.

Reading the code
----------------

Most modules carry a one-line docstring. Test cases live in the same file as the code
they cover, below a ``# test cases`` marker; integration tests live in
``tests/integration``.
