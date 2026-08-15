"""Errors staging raises, each naming the source it was reading or writing."""

from __future__ import annotations

from wiki_api.domain.errors import KnowledgeError


class StagingError(KnowledgeError):
    """Base class for anything that stops sources being staged or read back."""


class UpstreamMissing(StagingError):
    """A declared upstream file is not where the collector expects it."""

    def __init__(self, collector: str, path: str) -> None:
        super().__init__(
            f"{collector} cannot find {path}: check the submodules are checked out"
        )
        self.collector = collector
        self.path = path


class UpstreamUnreadable(StagingError):
    """The commit behind an upstream checkout cannot be read."""

    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"cannot tell which commit {path} is at: {detail}")
        self.path = path
        self.detail = detail


class UnknownCollector(StagingError):
    """Somebody asked for a collector nothing declares."""

    def __init__(self, name: str, declared: tuple[str, ...]) -> None:
        super().__init__(f"no collector called {name}; declared: {', '.join(declared)}")
        self.name = name
        self.declared = declared


class StagedFileMissing(StagingError):
    """The manifest lists a file that is not in the staged directory."""

    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is listed in the manifest but is not staged")
        self.path = path


class SharedTableUnreadable(StagingError):
    """A shared drop table states something the reader will not guess at."""

    def __init__(self, origin: str, detail: str) -> None:
        super().__init__(f"cannot read the shared table {origin}: {detail}")
        self.origin = origin
        self.detail = detail


class ManifestMissing(StagingError):
    """A build was asked to read a staged directory that was never staged."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"no staging manifest at {path}: run the staging command first"
        )
        self.path = path


class ManifestSchemaMismatch(StagingError):
    """The manifest was written by a staging step of a different schema."""

    def __init__(self, found: int, expected: int) -> None:
        super().__init__(
            f"the staged sources declare manifest schema {found}, "
            f"this build reads {expected}"
        )
        self.found = found
        self.expected = expected


# test cases


def test_every_staging_error_is_a_knowledge_error() -> None:
    errors = (
        UpstreamMissing("configs", "Server/data/configs/item_configs.json"),
        UpstreamUnreadable("game_data/2009scape", "not a repository"),
        UnknownCollector("prices", ("configs", "tables")),
        StagedFileMissing("configs/item_configs.json"),
        SharedTableUnreadable("RDT.xml", "the table states no rows"),
        ManifestMissing("data/source/sources.json"),
        ManifestSchemaMismatch(2, 1),
    )
    assert all(isinstance(error, StagingError) for error in errors)
    assert all(isinstance(error, KnowledgeError) for error in errors)


def test_an_unknown_collector_lists_the_ones_there_are() -> None:
    error = UnknownCollector("nothing", ("configs", "tables"))
    assert "configs" in str(error)
    assert "tables" in str(error)
