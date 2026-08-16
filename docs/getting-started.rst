Getting started
===============

Three steps: get a dataset, make a key, start something.

.. code-block:: bash

   scape2009-wiki-data pull                  # the dataset, once
   scape2009-wiki-keys init                  # the key this deployment answers, once
   scape2009-wiki-keys issue --label {label}      # a token, kept under tokens/{label}.json
   scape2009-wiki-serve                      # HTTP on :8000, contract at /docs

Ask it something:

.. code-block:: bash

   TOKEN=$(jq -r .access_token ~/.config/scape2009-wiki-api/tokens/{label}.json)
   curl -H "authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/entities/item/dragon-scimitar

``WIKI_API_AUTH_MODE=off`` answers to everyone.

Elsewhere the same four commands are ``scape2009-wiki-api <command>`` (container, frozen
build) or ``uv run poe <command>`` (checkout, with ``download-data`` for the dataset and
``serve-all`` to honour the ``surfaces`` setting).

MCP over stdio
--------------

Spawned by the client. No key: nothing checks one when the client is the parent process.

.. code-block:: json

   {"mcpServers": {"2009scape-wiki": {"type": "stdio",
     "command": "scape2009-wiki-mcp"}}}

That is PyPI or a system package. Otherwise:

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - installed as
     - ``command``, ``args``
   * - PyPI, no install
     - ``uvx``, ``["--from", "scape2009-wiki-api", "scape2009-wiki-mcp"]``
   * - a container
     - ``docker``, ``["run", "-i", "--rm", "arsalananwari/2009scape-wiki-api", "mcp"]``
   * - a checkout
     - ``uv``, ``["run", "--directory", "/path/to/repo", "--quiet", "scape2009-wiki-mcp"]``

All of them need a dataset. Check with ``scape2009-wiki-data where``.

MCP over HTTP
-------------

On its own port, where a key **is** checked:

.. code-block:: bash

   WIKI_API_MCP_TRANSPORT=http scape2009-wiki-mcp     # :8009

Or mounted inside the contract at ``/mcp``, one port and one token, which is
``surfaces=both`` and what the container serves:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

In a container
--------------

.. code-block:: bash

   docker run --rm -v ./config:/config arsalananwari/2009scape-wiki-api keys init
   docker run -p 8000:8000 -v ./config:/config arsalananwari/2009scape-wiki-api


From a checkout
---------------

``uv run poe container up`` does the four preparation steps that are
easy to get wrong: dataset, public key, a writable directory for bans, and a token. Then
``container check`` questions it and ``container down`` stops it. Takes ``--fixture``,
``--compose``, ``--open``.

Building the artifact
---------------------

Checkout only, and only when changing the pipeline. See :doc:`pipeline`.

.. code-block:: bash

   uv run poe sync-submodules             # check out the game repositories
   uv run poe build-artifacts             # the artifact and the test fixture
   uv run poe build-artifacts --offline   # no checkout, no prices, no network
