The HTTP contract
=================

A versioned FastAPI surface at ``/v1``. It returns render-ready JSON: every value
carries its own label, format and unit, so a front end never hard-codes a field name.

The OpenAPI document is at ``/openapi.json`` and the interactive contract at ``/docs``.
Both are covered by a contract test, so they do not drift.

Routes
------

============================================  =======================================================
path                                          what it answers
============================================  =======================================================
``/health``                                   Whether this process is up with a readable build open.
``/v1/about``                                 The manifest of the build being served.
``/v1/types``                                 Every type, with its attributes and relationships.
``/v1/types/{type}/entities``                 All entities of one type, a page at a time.
``/v1/types/{type}/compare``                  Entities whose stored number answers a question.
``/v1/search``                                Full text search across every type.
``/v1/find``                                  The one entity that goes by this name.
``/v1/near-names``                            Which real names a misspelt one might have meant.
``/v1/entities/{type}/{ref}``                 The whole page for one entity.
``/v1/entities/{type}/{ref}/tooltip``         The hover card.
``/v1/entities/{type}/{ref}/rel/{rel}``       One relationship, a page at a time.
``/v1/entities/{type}/{ref}/prices``          What it has been worth, week by week.
``/v1/entities/{type}/{ref}/resolve``         What a reference points at, without being sent there.
============================================  =======================================================

All routes are ``GET``. ``{ref}`` is an id or a slug: all digits is read as an id,
anything else as a slug, so ``/v1/entities/item/4587`` and
``/v1/entities/item/dragon-scimitar`` are the same page.

Paging
------

Every listing takes ``limit`` (default 50, ceiling 200), ``offset`` and ``sort``
(``name`` or ``id``). A response repeats the limit it used and gives ``next_offset``,
null when there is nothing more.

Pages
-----

An entity page comes back as a descriptor: identity, one line of description, an
infobox, the body split into sections, and one block per relationship the entity
actually has. Each block holds a label, the first page of rows, and the walk that
produced it.

A value pointing at another entity comes back as a whole link with type, id, slug and
label. Links never carry a URL, because the front end owns its own routing.

Absence
-------

A reference that does not resolve is an answer, not an exception.

found
    The body.

moved
    ``308`` to where the entity answers now, pointing at the same resource that was
    asked for. Asking for a tooltip redirects to a tooltip.

hidden
    ``404`` with code ``not_published``. It is in this build and deliberately not
    served.

missing
    ``404`` with code ``not_found``, carrying ``near_names_url``.

Errors
------

One envelope, carrying no stack trace, path or internal identifier:

.. code-block:: json

   {"error": {"code": "not_found", "message": "no such entity",
              "near_names_url": "/v1/near-names?name=dragon+scimtar&type=item"}}

Codes are ``not_found``, ``not_published``, ``invalid_request``,
``data_version_mismatch``, ``artifact_unavailable``, ``unauthenticated``, ``blocked``,
``throttled`` and ``unexpected``.

Caching
-------

A build never changes while it is being served, which is what the caching rests on.

- ``X-Data-Version`` names the build that answered.
- A weak ``ETag`` covers the build, the path and the sorted query, so the same question
  validates the same however the words were ordered.
- ``?v=<data_version>`` pins to a build. A pinned answer can never change, so it comes
  back ``public, max-age=31536000, immutable``. Pinning to a build no longer served is a
  ``data_version_mismatch`` naming the one that is.
- ``/health`` and ``/v1/about`` are never cached.
