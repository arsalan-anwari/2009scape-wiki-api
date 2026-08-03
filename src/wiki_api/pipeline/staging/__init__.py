"""Stage the game's own sources into the directory a build reads."""

from wiki_api.pipeline.staging.collectors import (
    CONFIGS,
    PRICES,
    TABLES,
    CollectorReport,
    StagingReport,
    StagingRun,
    stage,
)
from wiki_api.pipeline.staging.declared import (
    DECLARED_CONFIGS,
    DECLARED_TABLES,
    DeclaredConfig,
    DeclaredTable,
)
from wiki_api.pipeline.staging.errors import (
    ManifestMissing,
    ManifestSchemaMismatch,
    StagedFileMissing,
    StagingError,
    UnknownCollector,
    UpstreamMissing,
    UpstreamUnreadable,
)
from wiki_api.pipeline.staging.manifest import (
    MANIFEST_NAME,
    MANIFEST_SCHEMA,
    StagedFile,
    StagingManifest,
    digest_of,
    read_manifest,
    read_manifest_if_staged,
    write_manifest,
)
from wiki_api.pipeline.staging.prices import (
    SnapshotHarvest,
    SnapshotRef,
    download_snapshots,
    fetch_snapshots,
    snapshot_refs,
)
from wiki_api.pipeline.staging.upstream import game_version_of

__all__ = [
    "CONFIGS",
    "DECLARED_CONFIGS",
    "DECLARED_TABLES",
    "MANIFEST_NAME",
    "MANIFEST_SCHEMA",
    "PRICES",
    "TABLES",
    "CollectorReport",
    "DeclaredConfig",
    "DeclaredTable",
    "ManifestMissing",
    "ManifestSchemaMismatch",
    "SnapshotHarvest",
    "SnapshotRef",
    "StagedFile",
    "StagedFileMissing",
    "StagingError",
    "StagingManifest",
    "StagingReport",
    "StagingRun",
    "UnknownCollector",
    "UpstreamMissing",
    "UpstreamUnreadable",
    "digest_of",
    "download_snapshots",
    "fetch_snapshots",
    "game_version_of",
    "read_manifest",
    "read_manifest_if_staged",
    "snapshot_refs",
    "stage",
    "write_manifest",
]
