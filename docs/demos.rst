Demonstrations
==============

``demos/`` attaches a real model to the MCP server and records what came back. 
They show what the data can answer, and make a missing capability obvious.

=========================  ================================================================
demo                       what it shows
=========================  ================================================================
``claude_mcp_attach``      Five questions only answerable from this data, and the tools
                           reached for. The smallest one, and the one to run first.
``claude_fuzzy_match``     One question under a misspelt name close to two different sorts
                           of thing, settled by asking rather than guessing.
``claude_complex_query``   Forty-one probes, one per capability, run unattended and
                           tallied. Produces ``report.md``.
=========================  ================================================================

.. code-block:: bash

   uv run poe demo claude_complex_query --scripted     # the whole sweep, unattended
   uv run poe demo claude_complex_query --list         # what it asks, without asking
   uv run poe demo claude_complex_query --only fuzzy_name

Setting one up
--------------

Needs a build in ``data/`` (``uv run poe download-data``) and
``CLAUDE_CODE_OAUTH_TOKEN`` in a ``.env`` inside the demo folder, from
``claude setup-token``. An ``ANTHROPIC_API_KEY`` works too, billed per token. Every run
talks to a real model and costs what that credential is billed at.

Each demo spawns ``scape2009-wiki-mcp`` and talks to it down a pipe, with the dataset
path pinned by the script so a run cannot quietly answer from a different build. Nothing
is fetched, served over HTTP or containerised, and nothing listens on a port, so there
is no key to present.

Example output
--------------

``demos/claude_complex_query/report.md`` is the last committed run: a table of every
probe, then each question with its tool calls, answer and checks. The last one covered
41 of 41 probes in 10m 17s, calling all 32 tools at least once. One probe, trimmed:

.. code-block:: text

   Asked  How much is Statius's warhammer worth, how much can I trust that price,
          and what does it do for my strength?

   Did    get_thing(name="Statius's warhammer")
          how_the_price_moved(name="Statius's warhammer")

   Said   6,893,037 gp from 113 readings, confidence rated "traded" (genuine trade
          activity, not a guess). Up 353,037 gp (+5.4%) since 2024-06-08. Strength
          bonus +114, alongside +123 Crush (but -4 Stab and -4 Slash).

          Note there are separate entries for the degraded and corrupt versions of
          this hammer, which carry their own stats and prices.

Two things there come from the data model, not the model writing it: price confidence is
served alongside the number, and the closing line tells the related entries apart by
what the wiki records rather than by their ids.
