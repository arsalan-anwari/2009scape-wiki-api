CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE entity (
    search_id     INTEGER PRIMARY KEY,
    type          TEXT    NOT NULL,
    id            INTEGER NOT NULL,
    slug          TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    description   TEXT,
    source_key    TEXT,
    canonical_id  INTEGER,
    variant_kind  TEXT,
    searchable    INTEGER NOT NULL,
    visibility    TEXT    NOT NULL,
    hidden_reason TEXT,
    icon_ref      TEXT,
    attributes    TEXT    NOT NULL,
    source        TEXT    NOT NULL,
    source_ref    TEXT,
    game_version  TEXT    NOT NULL,
    UNIQUE (type, id),
    UNIQUE (type, slug),
    UNIQUE (type, source_key)
);

CREATE INDEX entity_by_type ON entity (type, name, id);

CREATE INDEX entity_by_canonical ON entity (type, canonical_id);

CREATE TABLE entity_alias (
    type       TEXT    NOT NULL,
    alias_slug TEXT    NOT NULL,
    entity_id  INTEGER NOT NULL,
    kind       TEXT    NOT NULL,
    PRIMARY KEY (type, alias_slug)
) WITHOUT ROWID;

CREATE TABLE edge (
    src_type      TEXT    NOT NULL,
    src_id        INTEGER NOT NULL,
    rel           TEXT    NOT NULL,
    dst_type      TEXT    NOT NULL,
    dst_id        INTEGER NOT NULL,
    discriminator TEXT    NOT NULL DEFAULT '',
    attributes    TEXT    NOT NULL,
    order_key     INTEGER NOT NULL DEFAULT 0,
    source        TEXT    NOT NULL,
    source_ref    TEXT,
    game_version  TEXT    NOT NULL,
    PRIMARY KEY (src_type, src_id, rel, dst_type, dst_id, discriminator)
);

CREATE INDEX edge_forward ON edge (src_type, src_id, rel, order_key);

CREATE INDEX edge_reverse ON edge (dst_type, dst_id, rel, order_key);

CREATE TABLE price_history (
    item_id       INTEGER NOT NULL,
    snapshot_date TEXT    NOT NULL,
    value         INTEGER NOT NULL,
    PRIMARY KEY (item_id, snapshot_date)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE entity_fts USING fts5 (
    name,
    aliases,
    description,
    tokenize = 'unicode61 remove_diacritics 2',
    prefix = '2 3'
);
