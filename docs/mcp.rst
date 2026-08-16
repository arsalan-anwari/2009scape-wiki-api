The MCP server
==============

The same knowledge, asked the way a model asks. Tools take names, not numbers. Answers
are far smaller than the HTTP ones, and one that cannot be given says what to do instead
of failing. See :doc:`demos` for worked examples.

Connecting
----------

Over stdio, which is what a local client spawns, and which asks for no key:

.. code-block:: json

   {"mcpServers": {"2009scape-wiki": {"type": "stdio",
     "command": "scape2009-wiki-mcp"}}}

Over HTTP, behind the same token as the wiki contract:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $TOKEN"

:doc:`getting-started` has the ``command`` and ``args`` for every other way of
installing it, and both transports in full.

Tools
-----

Eight are written by hand:

=========================  ==================================================================
tool                       what it answers
=========================  ==================================================================
``get_thing``              One thing by name, and a count of everything it is joined to.
``search``                 Find things by words from their name.
``list_things``            Everything of one sort, a page at a time.
``list_sorts``             The sorts this build knows about, and how many of each.
``compare_by_number``      One sort by a number it records, above or below a threshold.
``how_the_price_moved``    Which way one thing's worth has gone, and by how far.
``find_close_names``       Given a name that answered to nothing, the closest real names.
``about``                  Which build is being answered from.
=========================  ==================================================================

The rest are generated: one tool per relationship per direction, named from the
registry's own labels (``drops`` and ``dropped_by``, ``sells`` and ``sold_in``). A
relationship declared later becomes two new tools with nobody writing them; one with no
edges in this build is not offered. 32 tools on a current build.

Call ``get_thing`` first. Its counts name the tool that reads each one.

Answers
-------

Every answer is wrapped in an outcome, so a model never reads an exception.

===============  ==================================================================
``found``        ``result`` holds the answer.
``renamed``      That name is retired. The note gives the one to ask with.
``withheld``     In this build, but not published.
``unknown``      Nothing answers to that name. The note says how to settle it.
``ambiguous``    Several sorts answer to it; which was meant is for whoever asked.
===============  ==================================================================

Answers are paged, report the total, and declare a result-size ceiling, so a long drop
table cannot swallow a context window.

Two rules the server states up front
------------------------------------

**A ref is for calling with, not for saying.** Every answer carries a ``ref`` such as
``item:4587``, which is how a model names one exact thing back to a tool. A person
reading the answer has never seen one, so refs, ids, coordinates and region numbers
never belong in what the model says.

**A misspelling is not the model's to settle.** ``find_close_names`` answers with names
and identities alone: it exists to be shown to a person, not chosen from. Same for
things sharing a name. If nothing in the answer tells two apart, they are the same thing
to whoever asked.

.. code-block:: json

   {"outcome": "found",
    "result": {"of": "Dragon scimitar", "label": "Dropped by", "total": 1,
               "neighbours": [{"name": "King Black Dragon", "type": "npc", "id": 50,
                               "facts": {"Chance": "1/512"}}]}}

