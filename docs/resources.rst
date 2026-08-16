Where things live
=================

This project
------------

.. list-table::
   :widths: 40 60

   * - Source
     - https://github.com/arsalan-anwari/2009scape-wiki-api
   * - Releases, deb, rpm, Arch packages
     - https://github.com/arsalan-anwari/2009scape-wiki-api/releases
   * - Issues
     - https://github.com/arsalan-anwari/2009scape-wiki-api/issues
   * - PyPI
     - https://pypi.org/project/scape2009-wiki-api/
   * - Docker Hub
     - https://hub.docker.com/r/arsalananwari/2009scape-wiki-api
   * - Dataset
     - https://huggingface.co/datasets/arsalan-anwari/2009scape-wiki-api-data
   * - Documentation theme
     - https://github.com/arsalan-anwari/2009scape-sphinx-theme

A running instance serves its OpenAPI document at ``/openapi.json`` and the interactive
contract at ``/docs``.

Where the data comes from
-------------------------

Git submodules under ``game_data/``, mirrored from the 2009scape project. Nothing there
is written to; everything the build reads is staged into ``data/source`` first.

======================================  ==========================================================================
submodule                               what it holds
======================================  ==========================================================================
``2009scape``                           The server: configs, drop tables, the cache, and the code enums are in.
``rs09-constants-library``              The game's named id constants.
``2009scape-item-definition-editor``    Item definition data.
``rs09-thanos-tool``                    Cache tooling.
======================================  ==========================================================================

Grand Exchange snapshots come from ``https://cdn.2009scape.org/gedata/``.

Built on
--------

FastAPI and FastMCP for the surfaces, pydantic for the model and settings, uvicorn for
serving, huggingface-hub for the dataset, cryptography for Ed25519 keys, uv for
environments, locking and the build backend. Quality: ruff, mypy, import-linter, pytest.
Packaging: PyInstaller and nfpm.

Licence
-------

Apache-2.0. Not affiliated with Jagex. The game data belongs to the
`2009scape <https://2009scape.org/>`_ project.
