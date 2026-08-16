Getting started
===============

First run
---------

.. code-block:: bash

   uv sync --all-extras
   uv run poe download-data          # the published dataset into data/
   uv run poe keys init              # the key this deployment answers, once
   uv run poe keys issue --label me  # one token, saved under tokens/me.json
   uv run poe serve                  # HTTP on :8000, contract at /docs

Then ask it something:

.. code-block:: bash

   TOKEN=$(jq -r .access_token ~/.config/scape2009-wiki-api/tokens/me.json)
   curl -H "authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/entities/item/dragon-scimitar

Both surfaces refuse to start without a dataset and an issuer key, and say which is
missing. ``WIKI_API_AUTH_MODE=off`` answers everyone instead.

Use ``serve-all`` rather than ``serve`` when the process should honour the ``surfaces``
setting and serve MCP as well.

As an MCP server
----------------

The repository carries a ``.mcp.json``, so running ``claude`` inside the checkout offers
the server. Other clients spawn the console script:

.. code-block:: json

   {"mcpServers": {"2009scape-wiki": {"type": "stdio", "command": "uv",
     "args": ["run", "--directory", "/path/to/2009scape-wiki-api", "--quiet",
              "scape2009-wiki-mcp"]}}}

A running container is already an MCP server, tools at ``/mcp`` behind the same token:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki-docker http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $(uv run poe container token)"

Standalone over HTTP: ``WIKI_API_MCP_TRANSPORT=http WIKI_API_MCP_PORT=8009 uv run poe
mcp``. Keys are only asked for over HTTP, never over stdio.

In a container
--------------

.. code-block:: bash

   uv run poe container up      # build, prepare dataset and key, start
   uv run poe container check   # ask it what a deployment has to answer
   uv run poe container down    # stop and remove

``up`` fetches a dataset, places your public key, makes a writable directory for bans
and issues a token. It takes ``--fixture`` (serve the test fixture), ``--compose`` or
``--open`` (answer everyone), and ``check`` follows whichever was used.

Building the artifact
---------------------

Only needed when changing the pipeline.

.. code-block:: bash

   uv run poe sync-submodules             # check out the game repositories
   uv run poe build-artifacts             # the real artifact and the test fixture
   uv run poe build-artifacts --offline   # no checkout, no prices, no network
   uv run poe build-artifacts --fixture-only

See :doc:`pipeline` for what each stage does.
