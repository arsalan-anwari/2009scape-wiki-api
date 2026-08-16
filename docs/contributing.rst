Contributing
============

.. code-block:: bash

   git clone https://github.com/arsalan-anwari/2009scape-wiki-api
   cd 2009scape-wiki-api
   uv sync --all-extras
   uv run poe build-artifacts --fixture-only   # enough to run the tests

Requires `uv <https://docs.astral.sh/uv/>`_ and Python 3.12. The fixture artifact is a
small hand-made build the whole test suite runs against, so the real dataset is not
needed to work on the code.

The gate
--------

``uv run poe check`` is what CI runs, and it is five things:

=================  ======================================================
task               what it is
=================  ======================================================
``lint``           ruff, with E, F, I, UP, B, SIM and RUF selected.
``format-check``   ruff format, 88 columns.
``typecheck``      mypy in strict mode.
``imports``        import-linter, the six contracts in :doc:`architecture`.
``test``           pytest, with coverage over ``wiki_api``.
=================  ======================================================

``uv run poe fix`` runs the linter with ``--fix`` and then the formatter. CI also runs
``bash scripts/check_docs.sh`` separately.

Where tests live
----------------

Test cases live in the same file as the code they cover, below a ``# test cases``
marker. Guard tests enforce it: every module with tests declares where they start, none
hide above the marker, the marker appears once, and nothing shipped imports pytest at
module level. Tests that need pytest import it inside the function.

Integration tests, which cross module boundaries, live in ``tests/integration``.

Test names are sentences saying what should be true. Prefer
``test_a_variant_may_not_be_searchable`` over ``test_variant_searchable``.

How prose is checked
--------------------

``scripts/check_docs.sh`` reads Python comments, docstrings, description strings, prose
values in JSON, and ``README.md`` outside its code blocks. It reports characters outside
ASCII, each with what to type instead, and filler that reads as generated rather than
written.

.. code-block:: bash

   bash scripts/check_docs.sh          # the default paths
   bash scripts/check_docs.sh --rules  # what is checked, and why
   bash scripts/check_docs.sh docs/    # anything you name

A line carrying ``docs-check: ignore`` is left alone. MCP tool descriptions are read by
a model and docstrings by whoever picks the code up next, so both are part of what the
project ships.

Making a change
---------------

1. Branch off ``main``.
2. Make the change, with test cases in the same file.
3. ``uv run poe fix``, then ``uv run poe check``.
4. ``bash scripts/check_docs.sh``.
5. If it is user-visible, add a line under ``## [Unreleased]`` in ``CHANGELOG.md``.
6. Open a pull request.

If the change touches the pipeline, rebuild and read the report. Build determinism is
tested, and the usual cause of a failure is iteration order somewhere that should have
been sorted.

Documentation
-------------

These pages are reStructuredText in ``docs/``, built with the
`2009scape theme <https://github.com/arsalan-anwari/2009scape-sphinx-theme>`_.

.. code-block:: bash

   uv run poe docs             # write docs/out
   uv run poe docs --strict    # treat every warning as a failure
   uv run poe docs --serve     # build, then serve docs/out on :8080

Sphinx and the theme live in the ``docs`` dependency group, so they are not installed by
a plain ``uv sync``. ``docs/out`` is generated and is not committed.

Releasing
---------

``CHANGELOG.md`` is the only place a version is decided. The top heading carrying a
version number is the version being released; ``release.sh`` writes it into every file
that names one, and a guard test fails when they drift.

.. code-block:: bash

   uv run poe release sync      # the declared version into every file that names one
   uv run poe release build     # the gate, then wheel, packages and image
   uv run poe release verify    # install and question all of it, offline
   uv run poe release all --yes # build all four channels and push them

Run ``sync`` before committing. Publishing refuses on a dirty tree, off ``main``, on an
already tagged version, or with the gate red, and nothing is pushed without ``--yes``.

A release is the tag, PyPI, Docker Hub, and a GitHub release carrying the deb, rpm and
Arch packages, the image as a loadable file, and ``SHA256SUMS``. The executable is
frozen inside a Debian 12 container rather than on a developer machine, because a frozen
build runs on the glibc it was built against or newer.

``uv run poe check-packages`` installs each package in a clean container of the
distribution it targets and asks the installed commands the questions a user will ask
first.
