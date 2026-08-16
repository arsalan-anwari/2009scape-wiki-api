The knowledge model
===================

Everything served is an entity, a typed link between two entities, or a price series.
There is no second shape, which is what lets one front end draw a page for a type it has
never heard of. The model lives in ``wiki_api.domain`` and imports nothing but pydantic.

Entities
--------

Nine types: ``item``, ``npc``, ``shop``, ``quest``, ``location``, ``scenery``, ``task``,
``room``, ``music``.

An entity is identified by type plus an id unique within that type, written
``item:4587``. That pair never changes across rebuilds. Beyond identity it carries:

``slug``
    A readable name, unique within its type and derived deterministically so links do
    not rot. On a collision the lowest id keeps the bare slug; a variant never claims
    it.

``attributes``
    A model whose type is decided by the entity type. An item cannot carry npc
    attributes.

``provenance``
    Which source kind, which commit of the game repository, and optionally the file and
    record. Kinds are ``game_config``, ``game_code``, ``game_cache``,
    ``grand_exchange``, ``overlay``, ``fixture``.

``canonical_id`` and ``variant_kind``
    Set together on a duplicate: noted, bound, placeholder or plain duplicate. A variant
    is never searchable and points at the entity it duplicates.

``visibility`` and ``hidden_reason``
    A hidden entity stays in the build but is not served, and has to say why: unnamed,
    suppressed, duplicate or placeholder.

``source_key``
    For things the game names but never numbers, so an allocated id survives a rebuild.

Entities are frozen. Nothing edits one after it is built.

The attribute registry
----------------------

Every attribute field is annotated with what it means and how to show it. A field that
forgets raises at import.

.. code-block:: python

   ge_buy_limit: Annotated[
       int | None,
       AttributeMeta("Buy limit", AttributeGroup.TRADE, 30, AttributeFormat.INT),
   ] = None

The registry records a ``label``, ``group``, ``order``, ``format`` and ``unit``, plus
flags: ``display``, ``derived`` (worked out rather than read), ``prominent`` (belongs in
the overview box), ``technical`` (visible, but not for a model to repeat), ``totalled``,
``choices`` (read off the enum behind the field) and ``fields`` (the parts of a packed
value, each addressable on its own).

Two things follow. A front end never hard-codes a field name, because ``/v1/types``
hands it the whole registry. And a value pointing at another entity comes back as a
whole link rather than a bare id, because the format says it is a reference.

Relationships
-------------

Thirteen are declared, each with a label both ways round and the types it may join.

===================  =================  ================  =======================================  ============
relationship         forward            inverse           from                                     to
===================  =================  ================  =======================================  ============
``drops``            Drops              Dropped by        npc                                      item
``sells``            Sells              Sold in           shop                                     item
``staffed_by``       Staffed by         Runs shop         shop                                     npc
``rewards``          Rewards            Reward from       quest                                    item
``uses_ammunition``  Uses ammunition    Used by           item                                     item
``located_in``       Found in           Found here        npc, shop, item, quest, scenery, music    location
``part_of``          Part of            Contains          location                                 location
``yields``           Yields             Gathered from     scenery, npc                             item
``makes``            Makes              Made from         item                                     item
``requires``         Requires           Needed for        quest, task                              item, quest
``assigns``          Assigns            Assigned by       npc                                      task
``satisfied_by``     Satisfied by       Counts towards    task                                     npc
``heard_during``     Heard during       Music heard       music                                    quest
===================  =================  ================  =======================================  ============

Edges are validated against that table. A ``drops`` edge starting at an item is refused,
and so is one carrying the wrong attribute model.

Some links are the whole fact: ``staffed_by`` records nothing beyond somebody running
the shop. Others carry data. A drop keeps ``weight`` and ``denominator`` rather than a
rate, so a reader is shown an exact ``1/512``; the rate is a declared derived value, so
nobody divides two numbers and nothing writes it down as though a source had said it.

Two edges can join the same pair and still be different facts. Rather than a counter, an
edge is keyed by its own attributes: a placement by its tile, a drop by which table it
rolls on, a requirement by its kind. Reordering a source cannot move an edge onto a
different key.

Variants and totals
-------------------

The game numbers a noted item separately from the item it notes. Serving those as two
pages would split every answer, so a variant points at its canonical entity and stays
out of search. Walks travel over an entity and all its variants at once, which is why a
total in a walk answer can be trusted.

Prices
------

A weekly series per item covering roughly two years, carrying a confidence judged by how
the record itself moved: ``traded`` (genuine trade activity), ``static`` (never moved)
or ``untraded`` (nothing usable). That is served alongside the number, so an answer can
say how much it is worth believing.

The manifest
------------

Every artifact says what it is. ``data_version`` names the build and is what
``X-Data-Version`` reports and ``?v=`` pins to. ``schema_version`` is the layout, and a
surface refuses to open one it does not know. ``content_hash`` covers the whole
snapshot, which is how build determinism is tested. ``built_at`` and ``game_version``
say when it was written and from which commit.
