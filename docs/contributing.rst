Contributing
============

.. code-block:: bash

   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api
   uv sync --all-extras
   uv run poe build-artifacts --fixture-only   # enough to run the tests

The fixture is a small hand-made build the whole suite runs against, 
so the real dataset is not needed. Omit this flag for full artifact.

The gate
--------

``uv run poe check`` is what CI runs:

=================  ======================================================
``lint``           ruff, with E, F, I, UP, B, SIM and RUF selected.
``format-check``   ruff format, 88 columns.
``typecheck``      mypy in strict mode.
``imports``        import-linter, the seven contracts in :doc:`architecture`.
``test``           pytest, with coverage over ``wiki_api``.
=================  ======================================================

Where tests live
----------------

Unit tests are in the same file as the code, below a ``# test cases`` marker. 

Integration tests live in ``tests/integration``.

Test names are sentences saying what should be true 
(Example: ``test_a_variant_may_not_be_searchable``).

How prose is checked
--------------------

``scripts/check_docs.sh`` reads Python comments, docstrings, description strings, prose
in JSON, and ``README.md`` outside its code blocks. It reports non-ASCII characters with
what to type instead, and filler that reads as generated.

.. code-block:: bash

   bash scripts/check_docs.sh          # the default paths
   bash scripts/check_docs.sh --rules  # what is checked, and why
   bash scripts/check_docs.sh docs/    # anything you name


Making a change
---------------

1. Branch off ``main``.
2. Make the change, with test cases in the same file.
3. ``uv run poe fix``, then ``uv run poe check``.
4. ``bash scripts/check_docs.sh``.
5. If it is user-visible, add a line under ``## [Unreleased]`` in ``CHANGELOG.md``.
6. Open a pull request.

If the change touches the pipeline, rebuild and read the report.

Documentation
-------------

reStructuredText in ``docs/``, built with the
`2009scape theme <https://github.com/arsalan-anwari/2009scape-sphinx-theme>`_.

.. code-block:: bash

   uv run poe docs             # write docs/out
   uv run poe docs --strict    # every warning is a failure
   uv run poe docs --serve     # build, then serve on :8080

Sphinx and the theme are in the ``docs`` dependency group, so a plain ``uv sync`` skips
them. ``docs/out`` is generated, not committed.

Releasing
---------

``CHANGELOG.md`` is the only place a version is decided: the top heading carrying one is
the version being released. ``release.sh`` writes it into every file that names one, and
a guard test fails when they drift.

.. code-block:: bash

   uv run poe release sync      # the declared version into every file that names one
   uv run poe release build     # the gate, then wheel, packages and image
   uv run poe release verify    # install and question all of it, offline
   uv run poe release all --yes # build all four channels and push them

A release is the tag, PyPI, Docker Hub, and a GitHub release carrying the deb, rpm and
Arch packages, the image as a loadable file, and ``SHA256SUMS``. 

``uv run poe check-packages`` installs each package in a clean container of its target
distribution and asks the installed commands what a user asks first.
