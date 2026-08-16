Extending it
============

Most extensions are a declaration rather than a feature. The registries in
``wiki_api.domain`` are read by the pipeline, the repository, the core and both
surfaces, so declaring something once usually makes it turn up everywhere.

Adding an attribute
-------------------

Add a field to the attribute model for that type in ``domain/attributes.py``, annotated
with an ``AttributeMeta``. A field without one raises at import.

.. code-block:: python

   poison_damage: Annotated[
       int | None,
       AttributeMeta("Poison damage", AttributeGroup.COMBAT, 80, AttributeFormat.INT),
   ] = None

That is the whole change on the serving side: it now appears on the page descriptor, in
``/v1/types``, in the MCP answer, and in ``compare_by_number``. The adapter reading that
source still has to fill it in.

If the value is worked out rather than read, declare it as a computed field with
``derived=True``. That is how a drop chance is served without any source stating one.

Adding a relationship
---------------------

Three places, all in ``domain/relationships.py``:

1. A member on ``RelationshipType``.
2. An edge attribute model, and an entry in ``EDGE_ATTRIBUTE_MODELS``. If the link is
   the whole fact, the model is empty.
3. An entry in ``RELATIONSHIP_SPECS``: a label each way round, the types each end may
   hold, a group and an order.

If two edges can join the same pair and still be different facts, teach
``discriminator_of`` what tells them apart, keyed on the edge's own attributes rather
than a counter.

Neither surface needs touching. MCP tools are generated from ``RELATIONSHIP_SPECS``, and
the HTTP walk route takes the relationship as a path parameter.

Adding an entity type
---------------------

1. A member on ``EntityType`` in ``domain/identity.py``.
2. An attribute model, and an entry in ``ATTRIBUTE_MODELS``.
3. An entry in ``ENTITY_TYPE_META`` in ``domain/presentation.py``.
4. Whichever relationships may join it, in ``RELATIONSHIP_SPECS``.
5. An adapter producing entities of that type.
6. If the source names them but never numbers them, an entry in ``NUMBERED`` in
   ``pipeline/allocate.py`` and an identity file.

Adding a source
---------------

An adapter lives in ``pipeline/sources/``, reads only from ``StagedSources``, and
returns a ``SourceOutcome``: what it produced, plus what it could not read and why.

.. code-block:: python

   def read_things(staged: StagedSources) -> SourceOutcome: ...

Register it in ``pipeline/sources/registry.py`` in dependency order, and add any
declared table it reads to ``READ_TABLES`` there, or the build keeps reporting it as
unread. If it cannot read every record, declare a tolerance in ``pipeline/tolerance.py``
saying how many rows may go unread and why.

If the source is not staged yet, declare it in ``pipeline/staging/declared.py`` first.
Staging reads only what is declared there.

Writing an overlay
------------------

Overlays are the right tool when the game states something nowhere, or states it wrong.
See :doc:`pipeline` for the document shape. Three things to get right:

- **Precedence.** Hand-written corrections are ``10``. Two documents writing the same
  fact at the same precedence fail the build.
- **Define or patch.** A ``define`` states an entity that did not exist; a ``patch``
  corrects one that did, and only a patch may decline to state a name.
- **expects.** State what the correction believes the source still says, so the build
  reports it once that changes.

Adding a storage backend
------------------------

Implement ``KnowledgeRepository`` from ``repository/protocol.py`` and add it to
``repository/factory.py``, the only module allowed to name a concrete implementation.
The protocol is read only, every listing is paged, and a walk takes a set of keys so
variants travel with the canonical entity.

``tests/integration/test_repository_conformance.py`` runs the same suite against every
backend, so a new one is covered by existing tests. SQL for the SQLite backend lives in
``repository/sqlite/sql/`` as files; add one and ``queries.py`` loads it by name.

Adding an HTTP route
--------------------

Routes live in ``surfaces/http/routes/``: ``entities`` for something you can already
name, ``discovery`` for finding something you cannot, ``meta`` for facts about the
process. A route reads the reference, asks the core one question, and hands a non-answer
to ``absence.delivered``. Routes hold no query logic; if you are writing some, it
belongs in ``core``.

Build paths with ``surfaces/http/addressing.py`` so a redirect points at the resource
that was asked for. A new route needs a summary and a response description, because the
OpenAPI document is covered by a contract test.

Adding an MCP tool
------------------

Most tools should not be written. If the question is "follow this link", declare the
relationship and the tool generates itself.

Write one only for something no link can answer. Name it in ``WRITTEN_TOOLS`` in
``surfaces/mcp/naming.py``, the one place they are listed, and describe when to reach
for it rather than what it returns. Keep answers small; ``surfaces/mcp/projection.py``
exists to shrink what the core hands back.

Before opening a pull request
-----------------------------

.. code-block:: bash

   uv run poe check

See :doc:`contributing` for what that expects.
