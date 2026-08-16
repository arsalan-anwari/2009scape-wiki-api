Installing
==========

Only the PyPI package needs Python. The container and the system packages carry the
dataset, so an offline machine answers everything.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - you want
     - do this
   * - a Python environment
     - ``uv tool install scape2009-wiki-api``
   * - a container
     - ``docker run -p 8000:8000 arsalananwari/2009scape-wiki-api``
   * - Debian, Ubuntu
     - ``sudo apt install ./scape2009-wiki-api_*_amd64.deb``
   * - Fedora, RHEL
     - ``sudo dnf install ./scape2009-wiki-api-*.x86_64.rpm``
   * - Arch
     - ``sudo pacman -U scape2009-wiki-api-*-x86_64.pkg.tar.zst``
   * - to work on it
     - clone the repository, see :doc:`contributing`

Packages are on the `releases page
<https://github.com/arsalan-anwari/2009scape-wiki-api/releases>`_ and run on Debian 12,
Ubuntu 22.04, RHEL 9 and newer.

From PyPI
---------

Requires Python 3.12. The package does not carry the dataset, so the first run fetches
it from Hugging Face into ``WIKI_API_DATA_DIR``. Three commands are installed:

``scape2009-wiki-serve``
    Serve HTTP, MCP, or both, depending on ``WIKI_API_SURFACES``.

``scape2009-wiki-mcp``
    The MCP tools alone, over stdio. This is what an MCP client spawns.

``scape2009-wiki-keys``
    Make the issuer key and issue tokens. See :doc:`access`.

Two extras exist: ``pipeline`` adds what the offline build needs, ``demos`` adds the
Claude agent SDK. Neither is needed to serve a built dataset.

As a container
--------------

The published image carries the dataset at ``/data``, so it serves with nothing
mounted. Keys and ``deploy.json`` are read from ``/config``.

.. code-block:: bash

   docker run -p 8000:8000 -v ./run/config:/config \
     arsalananwari/2009scape-wiki-api:1.0.0

Copy ``deploy.example.json`` rather than passing a dozen environment variables. Mounting
over ``/data`` is how a newer image serves an older build.

As a system package
-------------------

.. code-block:: bash

   sudo apt install ./scape2009-wiki-api_1.0.0_amd64.deb
   sudo scape2009-wiki-keys init
   sudo scape2009-wiki-keys issue --label me
   sudo systemctl enable --now scape2009-wiki-api

The unit ships stopped on purpose: a deployment answers only key holders, and there is
no key until you make one. Nothing on the machine needs Python, uv or a network.

From a checkout
---------------

.. code-block:: bash

   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api
   uv sync --all-extras

Requires `uv <https://docs.astral.sh/uv/>`_. Carry on to :doc:`getting-started`.
