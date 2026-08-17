2009scape wiki API
==================

Turns the 2009scape game sources into one immutable SQLite artifact, served two ways
from the same process: a versioned FastAPI contract for a wiki front end, and an MCP
server for Claude and other agents.

Nothing is hand-written but a small set of overlay corrections. Every fact traces back
to the game file it came from, and the same inputs produce the same bytes.

What a build holds
------------------

Around 20,000 entities, 83,000 relationships and two years of weekly Grand Exchange
prices, published to Hugging Face and never committed here.

==================  ======
sort                count
==================  ======
items                6,000
npcs                 3,100
scenery              1,850
music tracks           550
shops                  233
locations              210
quests                 150
slayer tasks            93
construction rooms      27
==================  ======

The two surfaces
----------------

HTTP returns everything a renderer needs. Each value carries its label, format and unit,
so a front end can draw a page for a type it has never heard of.

.. code-block:: json

   {"link": {"type": "item", "id": 536, "slug": "dragon-bones",
             "label": "Dragon bones"},
    "attributes": [{"key": "chance", "value": 0.5, "label": "Chance",
                    "format": "rate", "derived": true}]}

MCP answers the same question in far fewer words, takes names rather than numbers, and
says what it left out.

.. code-block:: json

   {"outcome": "found",
    "result": {"of": "Dragon scimitar", "label": "Dropped by", "total": 1,
               "neighbours": [{"name": "King Black Dragon", "type": "npc", "id": 50,
                               "facts": {"Chance": "1/512"}}]}}

.. toctree::
   :maxdepth: 2
   :caption: Using it

   install
   deployment
   configuration
   access

.. toctree::
   :maxdepth: 2
   :caption: The surfaces

   http-api
   mcp
   demos

.. toctree::
   :maxdepth: 2
   :caption: How it works

   architecture
   data-model
   pipeline

.. toctree::
   :maxdepth: 2
   :caption: Working on it

   extending
   contributing
   resources
