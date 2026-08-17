Installing
==========

Five ways in. Each is complete on its own: dataset, settings file, keys, commands.
See `The four commands` below to get started with the one you chose, and 
:doc:`access` for how to make and use keys.

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
     - ``docker pull arsalananwari/2009scape-wiki-api``
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


uv tool
-------

Config in ``~/.config/scape2009-wiki-api``, dataset in
``~/.local/share/scape2009-wiki-api``.

``scape2009-wiki-data pull`` writes to ``WIKI_API_DATA_DIR``, and ``--artifact-only``
skips the staged sources.

System package
--------------

Config in ``/etc/scape2009-wiki-api``, dataset in ``/usr/share/scape2009-wiki-api``.

The package brings the dataset, a ``scape2009-wiki`` service account, and a systemd unit
that runs as it. Settings are ``/etc/scape2009-wiki-api/deploy.json``, kept across
upgrades. ``sudo scape2009-wiki-data pull`` replaces the installed dataset with a newer
one.

Container
---------

Config in ``/config``, dataset in ``/data`` and already in the image.

Checkout
--------

Config in ``~/.config/scape2009-wiki-api``, dataset in ``data/`` rather than the shared
directory, which the ``poe`` tasks set for you.

.. code-block:: bash

   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api && uv sync --all-extras

Carry on to :doc:`deployment`.
