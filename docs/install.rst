Installing
==========

Five ways in. Each is complete on its own: dataset, settings file, keys, commands.

.. list-table::
   :header-rows: 1
   :widths: 26 42 32

   * - you want
     - install with
     - dataset
   * - a Python environment
     - ``uv tool install scape2009-wiki-api``
     - ``scape2009-wiki-data pull``
   * - a container
     - ``docker run -p 8000:8000 arsalananwari/2009scape-wiki-api``
     - in the image
   * - Debian, Ubuntu
     - ``sudo apt install ./scape2009-wiki-api_*_amd64.deb``
     - in the package
   * - Fedora, RHEL
     - ``sudo dnf install ./scape2009-wiki-api-*.x86_64.rpm``
     - in the package
   * - Arch
     - ``sudo pacman -U scape2009-wiki-api-*-x86_64.pkg.tar.zst``
     - in the package
   * - to work on it
     - clone it, see :doc:`contributing`
     - ``uv run poe download-data``

Packages and the image file are on the `releases page
<https://github.com/arsalan-anwari/2009scape-wiki-api/releases>`_. They run on Debian 12,
Ubuntu 22.04, RHEL 9 and newer.

The four commands
-----------------

=========  ===============================================================
``serve``  the HTTP contract, the tools, or both, as the settings ask
``mcp``    the tools alone, over stdio or HTTP
``keys``   make an issuer key, issue a token, withdraw one
``data``   fetch the published dataset, or say where one is looked for
=========  ===============================================================

PyPI and system packages put each on the PATH as ``scape2009-wiki-serve``,
``-mcp``, ``-keys``, ``-data``. The container and the frozen build take the name as an
argument: ``scape2009-wiki-api data pull``. see :doc:`configuration`.

PyPI
----

.. code-block:: bash

   uv tool install scape2009-wiki-api
   scape2009-wiki-data pull      # into ~/.local/share/scape2009-wiki-api
   scape2009-wiki-data where     # which build is there

``pull`` writes to ``WIKI_API_DATA_DIR``. ``--artifact-only`` skips the staged sources.
Extras: ``pipeline`` for the offline build, ``demos`` for the Claude agent SDK. Neither
is needed to serve.

Container
---------

Dataset at ``/data``, keys and ``deploy.json`` at ``/config``.

.. code-block:: bash

   docker run --rm -v ./config:/config arsalananwari/2009scape-wiki-api keys init
   docker run -p 8000:8000 -v ./config:/config arsalananwari/2009scape-wiki-api

The entrypoint is the dispatcher and the default command is ``serve``. Mount over
``/data`` to serve a different build.

System package
--------------

.. code-block:: bash

   sudo apt install ./scape2009-wiki-api_1.1.0_amd64.deb
   sudo scape2009-wiki-keys init
   sudo scape2009-wiki-keys issue --label me
   sudo systemctl enable --now scape2009-wiki-api

Settings are at ``/etc/scape2009-wiki-api/deploy.json``.  
Use ``scape2009-wiki-data pull`` to replace the installed dataset with a newer one.

Checkout
--------

.. code-block:: bash

   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api && uv sync --all-extras

A checkout keeps its dataset in ``data/``, not the shared directory. 
Carry on to :doc:`getting-started`.
