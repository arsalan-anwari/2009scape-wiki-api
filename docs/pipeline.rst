The build pipeline
==================

The build pipeline reads the game repositories, decodes the client cache, applies overlays, 
and writes the SQLite artifact that the server serves.

1. Staging
----------

``uv run poe stage-sources``

The game repositories are git submodules under ``game_data/``, never written to. Staging
copies out of them into ``data/source``, the only directory the build reads. Everything
needing a network, a checkout or a decoder happens here, so the build itself is pure.

Four kinds of sources:

==================  =============================================================
Config files        JSON and XML shipped beside the game server, copied
                    unchanged: item, npc and shop configs, drop tables, and the
                    shared tables many drop lists roll on.
Declared tables     Facts the game states only in code. ``pipeline/enums`` reads
                    a Kotlin or Java enum as a table with named columns, with its
                    own lexer, so it reads the declaration rather than running
                    anything. Also named id constants and quest requirements.
The game cache      ``pipeline/cache`` decodes the client cache against the
                    game's own definition classes: items from index 19, npcs 18,
                    scenery 16, landscape 5, world map labels 23. Map containers
                    are decrypted with the game's XTEA keys. The gazetteer comes
                    from here.
Prices              ``uv run poe fetch-ge``, weekly snapshots from the 2009scape
                    CDN.
==================  =============================================================

Staging records what it read and from which commit, so a later build reports drift.

2. Numbering
------------

``uv run poe allocate-ids --write``

The sources name quests, slayer tasks, locations and rooms but never number them. Each
gets a file under ``identity/`` mapping a stable natural key to a number, so links
survive a change in source order. Reading is the default; new numbers need ``--write``,
so the change lands in a diff a reviewer sees.

3. Adapters
-----------

One adapter per source in ``pipeline/sources``, turning staged records into entities and
edges, run in dependency order.

A record an adapter cannot read is counted, not dropped. ``pipeline/tolerance.py``
declares how much of each source may go unread and why; a build leaving more than that
fails. The registry also names tables nothing reads yet, and tables nothing reads
because the artifact already holds what they say.

4. Merge and write
------------------

``uv run poe build-artifact``

Adapter output and overlay documents merge into one in-memory snapshot, hashed, then
written to SQLite with the SQL kept in files. The artifact holds entities, edges,
aliases, prices, an FTS5 index and a manifest.

Overlays
~~~~~~~~

``overlays/`` holds hand-written JSON corrections, merged over the sources at build
time: where a fact the game states nowhere gets stated, and a plainly wrong record gets
fixed.

.. code-block:: json

   {"schema": 1, "source": "overlay", "precedence": 10,
    "game_version": "2009scape@2419bdb",
    "entities": [{"type": "item", "id": 14422,
                  "name": "Sacred clay pouch (class 1)",
                  "attributes": {"tradeable": "true"},
                  "expects": {"name": "USDT Slot"}}]}

Precedence, highest winning: ``DECLARED`` (0) from the game's declarations, ``DECODED``
(1) from the cache, ``PROPOSED`` (5), ``AUTHORED`` (10) by hand. Two documents writing
one fact at the same precedence fail the build rather than one silently winning.

An entry is a ``define`` for an entity that did not exist, or a ``patch`` for one that
did. ``expects`` states what the correction believes the source still says, so the build
reports it once upstream is fixed. A correction cannot outlive its problem.

The report
~~~~~~~~~~

A build reports entity and edge counts, overlays applied and expectations met, which
sources drifted, which tables are unread, and how close each tolerance came to its
ceiling.

Commands
--------

.. code-block:: bash

   uv run poe build-artifacts             # the real artifact and the test fixture
   uv run poe build-artifacts --offline   # no checkout, no prices, no network
   uv run poe build-artifacts --fixture-only
   uv run poe upload-data                 # publish it to Hugging Face
   uv run poe download-data               # fetch the published one back

