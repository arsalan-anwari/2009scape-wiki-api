Extending it
============

Most extensions are a declaration, not a feature. The registries in ``wiki_api.domain``
are read by the pipeline, the repository, the core and both surfaces, so declaring
something once makes it turn up everywhere.

Adding an attribute
-------------------

Add a field to that type's model in ``domain/attributes.py``, annotated with an
``AttributeMeta``. A field without one raises at import.

.. code-block:: python

   poison_damage: Annotated[
       int | None,
       AttributeMeta("Poison damage", AttributeGroup.COMBAT, 80, AttributeFormat.INT),
   ] = None

A value worked out rather than read is a computed field with ``derived=True``. That is
how a drop chance is served without any source stating one.

Adding a relationship
---------------------

Three places in ``domain/relationships.py``:

1. A member on ``RelationshipType``.
2. An edge attribute model and an entry in ``EDGE_ATTRIBUTE_MODELS``. Empty if the link
   is the whole fact.
3. An entry in ``RELATIONSHIP_SPECS``: a label each way round, the types each end may
   hold, a group and an order.

If two edges can join the same pair and still be different facts, teach
``discriminator_of`` what tells them apart, keyed on the edge's attributes rather than a
counter.

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

Register it in ``pipeline/sources/registry.py`` in dependency order and add any declared
table it reads to ``READ_TABLES``, or the build keeps reporting that table as unread. If
it cannot read every record, declare a tolerance in ``pipeline/tolerance.py``. A source
not staged yet goes in ``pipeline/staging/declared.py`` first; staging reads only what
is declared there.

Writing an overlay
------------------

For when the game states something nowhere, or states it wrong. Document shape is in
:doc:`pipeline`. Three things to get right:

- **Precedence.** Hand-written is ``10``. Two documents writing one fact at the same
  precedence fail the build.
- **Define or patch.** A ``define`` states an entity that did not exist; a ``patch``
  corrects one that did, and only a patch may decline to state a name.
- **expects.** What the correction believes the source still says, so the build reports
  it once that changes.

Adding a storage backend
------------------------

Implement ``KnowledgeRepository`` from ``repository/protocol.py`` and add it to
``repository/factory.py``, the only module allowed to name a concrete implementation.
The protocol is read only, every listing is paged, and a walk takes a set of keys so
variants travel with the canonical entity.

``tests/integration/test_repository_conformance.py`` runs one suite against every
backend, so a new one is covered already. SQLite SQL lives in
``repository/sqlite/sql/`` as files; 
add one and add it to ``queries.py`` so it can be loaded by name.

Adding an HTTP route
--------------------

In ``surfaces/http/routes/``: 
- ``entities`` for something you can name
- ``discovery`` for finding something you cannot
- ``meta`` for facts about the process. 

A route reads the reference, asks the core one question, and hands a non-answer 
to ``absence.delivered``. Query logic belongs in ``core``, never here.

Build paths with ``surfaces/http/addressing.py`` so a redirect points at the resource
asked for. A new route needs a summary and a response description: the OpenAPI document
is covered by a contract test.

Adding an MCP tool
------------------

Most should not be written. If the question is "follow this link", declare the
relationship and the tool generates itself.

Write one only for what no link can answer. Name it in ``WRITTEN_TOOLS`` in
``surfaces/mcp/naming.py``, and describe when to reach for it rather than what it
returns. Keep answers small; ``surfaces/mcp/projection.py`` exists to shrink what the
core hands back.

Before opening a pull request
-----------------------------

.. code-block:: bash

   uv run poe check

See :doc:`contributing` for what that expects.
