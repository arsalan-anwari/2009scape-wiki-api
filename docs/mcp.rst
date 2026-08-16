The MCP server
==============

The same knowledge, asked the way a model asks. Every tool takes a name rather than a
number, answers are far smaller than the HTTP ones, and an answer that cannot be given
says what to do instead of failing. Built with `FastMCP <https://gofastmcp.com/>`_, and
read only.

Connecting
----------

Over stdio, which is what a local client spawns:

.. code-block:: json

   {"mcpServers": {"2009scape-wiki": {"type": "stdio", "command": "uv",
     "args": ["run", "--directory", "/path/to/2009scape-wiki-api", "--quiet",
              "scape2009-wiki-mcp"]}}}

Over HTTP against a running container, behind the same token as the wiki contract:

.. code-block:: bash

   claude mcp add --transport http 2009scape-wiki-docker http://127.0.0.1:8000/mcp/ \
     --header "authorization: Bearer $(uv run poe container token)"

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

The rest are generated. For every relationship the build holds, one tool per direction,
named from the registry's own label: ``drops`` and ``dropped_by``, ``sells`` and
``sold_in``, and so on. A relationship declared later turns up as two new tools without
anybody writing them, and one this build holds no edges for is not offered at all. That
gives 32 tools on a current build.

``get_thing`` is the tool to call first: its counts name the tool that reads each one.

Answers
-------

Every answer is wrapped in an outcome, so a model never reads an exception.

``found``
    ``result`` holds the answer.

``renamed``
    That name is retired. The note gives the one to ask with.

``withheld``
    In this build, but not published.

``unknown``
    Nothing answers to that name. The note explains how to settle it.

``ambiguous``
    Several sorts answer to that name, and which was meant is for whoever asked to say.

Answers are paged, report the total, and declare a result-size ceiling, so a long drop
table cannot swallow a context window.

Two rules the server states up front
------------------------------------

**A ref is for calling with, not for saying.** Every answer carries a ``ref`` such as
``item:4587``. It is how a model names one exact thing back to a tool. A person reading
the answer has never seen one, so refs, bare ids, coordinates and region numbers never
belong in what the model says.

**A misspelling is not the model's to settle.** ``find_close_names`` answers with names
and identities alone, on purpose: it exists to be shown to a person, not chosen from.
The same goes for things sharing a name. If nothing in the answer tells two things
apart, they are the same thing to whoever asked.

.. code-block:: json

   {"outcome": "found",
    "result": {"of": "Dragon scimitar", "label": "Dropped by", "total": 1,
               "neighbours": [{"name": "King Black Dragon", "type": "npc", "id": 50,
                               "facts": {"Chance": "1/512"}}]}}

A drop rate comes back as ``1/512`` because the edge kept the weight and the
denominator. See :doc:`demos` for worked examples.
