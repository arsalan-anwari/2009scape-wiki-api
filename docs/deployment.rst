Deployment
==========

Find how you installed it below and follow that section alone. 

All four end in the same place. The contract and the tools on ``:8000``, answering key
holders and nobody else, tools at ``/mcp/``.

==================  ==================================  ==================================
installed as        config                              dataset
==================  ==================================  ==================================
uv tool             ``~/.config/scape2009-wiki-api``    ``~/.local/share/scape2009-wiki-api``
system package      ``/etc/scape2009-wiki-api``         ``/usr/share/scape2009-wiki-api``
container           ``/config`` (a volume)              ``/data`` (in the image)
checkout            ``~/.config/scape2009-wiki-api``    ``data/``
==================  ==================================  ==================================

uv tool
-------

.. code-block:: bash

   # 1. install
   uv tool install scape2009-wiki-api

   # 2. the dataset, once
   scape2009-wiki-data pull
   scape2009-wiki-data where

   # 3. the key this deployment answers, and one token to call it with
   scape2009-wiki-keys init
   scape2009-wiki-keys issue --label me

   # 4. start it
   scape2009-wiki-serve

Ask it something, in another terminal:

.. code-block:: bash

   TOKEN=$(jq -r .access_token ~/.config/scape2009-wiki-api/tokens/me.json)
   curl -H "authorization: Bearer $TOKEN" \
     http://127.0.0.1:8000/v1/entities/item/dragon-scimitar

Connect an MCP client:

.. code-block:: bash

   # over http, behind the same token as the contract
   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

   # or over stdio, spawned by the client: no key, no port, nothing running
   claude mcp add --transport stdio 2009scape-wiki -- scape2009-wiki-mcp

System package
--------------

The dataset, a service account and a systemd unit all come with the package.

.. code-block:: bash

   # 1. install
   sudo dnf install ./scape2009-wiki-api-1.1.1-1.x86_64.rpm            # Fedora, RHEL
   # sudo apt install ./scape2009-wiki-api_1.1.1-1_amd64.deb           # Debian, Ubuntu
   # sudo pacman -U scape2009-wiki-api-1.1.1-1-x86_64.pkg.tar.zst      # Arch

   # 2. the dataset is already in /usr/share/scape2009-wiki-api

   # 3. the key and a token, as root: they belong to /etc, not to you
   sudo scape2009-wiki-keys init
   sudo scape2009-wiki-keys issue --label me

   # 4. start it
   sudo systemctl enable --now scape2009-wiki-api

Ask it something:

.. code-block:: bash

   TOKEN=$(sudo jq -r .access_token /etc/scape2009-wiki-api/tokens/me.json)
   curl -H "authorization: Bearer $TOKEN" \
     http://127.0.0.1:8000/v1/entities/item/dragon-scimitar

Connect an MCP client:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

   claude mcp add --transport stdio 2009scape-wiki -- scape2009-wiki-mcp

Settings are ``/etc/scape2009-wiki-api/deploy.json``, read by the service account rather
than by you. ``sudo scape2009-wiki-data pull`` replaces the installed dataset with a
newer one.

Container
---------

.. code-block:: bash

   # 1. a volume for the key and the addresses the guard refuses
   docker volume create wiki-config

   # 2. the dataset is already in the image, at /data

   # 3. the key and a token. Copy the token from what this prints
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api keys init
   docker run --rm -v wiki-config:/config arsalananwari/2009scape-wiki-api \
     keys issue --label me

   # 4. start it
   docker run -d -p 8000:8000 -v wiki-config:/config \
     arsalananwari/2009scape-wiki-api

Ask it something:

.. code-block:: bash

   TOKEN=<the token step 3 printed>
   curl -H "authorization: Bearer $TOKEN" \
     http://127.0.0.1:8000/v1/entities/item/dragon-scimitar

Connect an MCP client:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

   # or over stdio, one container per client, no key and no port
   claude mcp add --transport stdio 2009scape-wiki -- \
     docker run -i --rm arsalananwari/2009scape-wiki-api mcp


Keeping the signing key out of the container
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``keys init`` in the container leaves the signing key in the volume. Fine on one
machine, wrong for a real deployment. 

Use the Python package or Repo tools to make the keyon the system and pass the 
public key into the container using ``WIKI_API_AUTH_PUBLIC_KEY``. 

.. code-block:: bash

   scape2009-wiki-keys init # using python tools, or uv run poe keys init
   scape2009-wiki-keys issue --label the-wiki

   docker run -p 8000:8000 \
     -e "WIKI_API_AUTH_PUBLIC_KEY=$(cat ~/.config/scape2009-wiki-api/issuer.pub)" \
     arsalananwari/2009scape-wiki-api

Persistent bans and revocations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bans are then written inside the container and forgotten when it goes. Give it an empty
``/config`` volume to keep them, and no key goes in it:

.. code-block:: bash

   docker volume create wiki-state
   docker run -d --name wiki -p 8000:8000 \
     -e "WIKI_API_AUTH_PUBLIC_KEY=$(cat ~/.config/scape2009-wiki-api/issuer.pub)" \
     -v wiki-state:/config \
     arsalananwari/2009scape-wiki-api

Mount it at ``/config`` as that one exists in the image already, owned by the user 
it runs as.

Serving a different build, or answering everyone
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # a dataset of your own over the one in the image
   docker run -p 8000:8000 -v wiki-config:/config \
     -v ./data:/data:ro,z arsalananwari/2009scape-wiki-api

   # no key asked of anyone: a local front end, never anything reachable
   docker run -p 8000:8000 \
     -e WIKI_API_AUTH_MODE=off -e 'WIKI_API_CORS_ORIGINS=["*"]' \
     arsalananwari/2009scape-wiki-api


Checkout
--------

.. code-block:: bash

   # 1. install
   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api && uv sync --all-extras

   # 2. the dataset, into data/
   uv run poe download-data

   # 3. the key and a token
   uv run poe keys init
   uv run poe keys issue --label me

   # 4. start it
   uv run poe serve-all

Ask it something:

.. code-block:: bash

   TOKEN=$(jq -r .access_token ~/.config/scape2009-wiki-api/tokens/me.json)
   curl -H "authorization: Bearer $TOKEN" \
     http://127.0.0.1:8000/v1/entities/item/dragon-scimitar

Connect an MCP client:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

   claude mcp add --transport stdio 2009scape-wiki -- \
     uv run --directory /path/to/repo --quiet scape2009-wiki-mcp
