"""Turn staged sources into the documents a build merges."""

from wiki_api.pipeline.sources.coercion import Skipped, SkipReason
from wiki_api.pipeline.sources.errors import (
    AdapterError,
    ConflictingRecords,
    MalformedSourceValue,
    UnallocatedIdentity,
    UnknownSourceField,
)
from wiki_api.pipeline.sources.outcome import SourceOutcome
from wiki_api.pipeline.sources.overridden import Overridden, overridden_by
from wiki_api.pipeline.sources.quests import source_keys
from wiki_api.pipeline.sources.registry import places_in, read_sources
from wiki_api.pipeline.sources.staged import StagedSources

__all__ = [
    "AdapterError",
    "ConflictingRecords",
    "MalformedSourceValue",
    "Overridden",
    "SkipReason",
    "Skipped",
    "SourceOutcome",
    "StagedSources",
    "UnallocatedIdentity",
    "UnknownSourceField",
    "overridden_by",
    "places_in",
    "read_sources",
    "source_keys",
]
