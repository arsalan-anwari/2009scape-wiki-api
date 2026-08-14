"""Read the sources that say where part of the world is, and what it is called."""

from wiki_api.pipeline.places.gazetteer import Gazetteer, Place
from wiki_api.pipeline.places.names import folded

__all__ = [
    "Gazetteer",
    "Place",
    "folded",
]
