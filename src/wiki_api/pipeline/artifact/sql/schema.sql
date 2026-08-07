-- The artifact is downloaded at runtime rather than built by the process that reads
-- it, so every column backed by a domain vocabulary states that vocabulary here. A
-- drift test keeps these lists identical to the Python enums.

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE entity (
    search_id     INTEGER PRIMARY KEY,
    type          TEXT    NOT NULL
        CHECK (type IN ('item', 'npc', 'shop', 'quest', 'location')),
    id            INTEGER NOT NULL,
    slug          TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    description   TEXT,
    source_key    TEXT,
    canonical_id  INTEGER,
    variant_kind  TEXT
        CHECK (variant_kind IN ('noted', 'bound', 'placeholder', 'duplicate')),
    searchable    INTEGER NOT NULL CHECK (searchable IN (0, 1)),
    visibility    TEXT    NOT NULL
        CHECK (visibility IN ('published', 'hidden')),
    hidden_reason TEXT
        CHECK (hidden_reason IN ('unnamed', 'suppressed', 'duplicate', 'placeholder')),
    icon_ref      TEXT,
    attributes    TEXT    NOT NULL,
    source        TEXT    NOT NULL
        CHECK (source IN
            ('game_config', 'game_code', 'game_cache', 'grand_exchange', 'overlay',
             'fixture')),
    source_file   TEXT,
    source_ref    TEXT,
    game_version  TEXT    NOT NULL,
    UNIQUE (type, id),
    UNIQUE (type, slug),
    UNIQUE (type, source_key)
);

CREATE INDEX entity_by_type ON entity (type, name, id);

CREATE INDEX entity_by_canonical ON entity (type, canonical_id);

CREATE TABLE entity_alias (
    type       TEXT    NOT NULL
        CHECK (type IN ('item', 'npc', 'shop', 'quest', 'location')),
    alias_slug TEXT    NOT NULL,
    entity_id  INTEGER NOT NULL,
    kind       TEXT    NOT NULL
        CHECK (kind IN ('retired_slug', 'shorthand', 'alternate_name')),
    PRIMARY KEY (type, alias_slug)
) WITHOUT ROWID;

CREATE TABLE edge (
    src_type      TEXT    NOT NULL
        CHECK (src_type IN ('item', 'npc', 'shop', 'quest', 'location')),
    src_id        INTEGER NOT NULL,
    rel           TEXT    NOT NULL
        CHECK (rel IN ('drops', 'sells', 'staffed_by', 'rewards', 'uses_ammunition',
                       'located_in', 'part_of')),
    dst_type      TEXT    NOT NULL
        CHECK (dst_type IN ('item', 'npc', 'shop', 'quest', 'location')),
    dst_id        INTEGER NOT NULL,
    discriminator TEXT    NOT NULL DEFAULT '',
    attributes    TEXT    NOT NULL,
    order_key     INTEGER NOT NULL DEFAULT 0,
    source        TEXT    NOT NULL
        CHECK (source IN
            ('game_config', 'game_code', 'game_cache', 'grand_exchange', 'overlay',
             'fixture')),
    source_file   TEXT,
    source_ref    TEXT,
    game_version  TEXT    NOT NULL,
    PRIMARY KEY (src_type, src_id, rel, dst_type, dst_id, discriminator)
);

CREATE INDEX edge_forward ON edge (src_type, src_id, rel, order_key);

CREATE INDEX edge_reverse ON edge (dst_type, dst_id, rel, order_key);

CREATE TABLE price_history (
    item_id       INTEGER NOT NULL,
    -- SQLite has no date type; the range scan in select_price_history.sql compares
    -- these as text, which is only correct while they stay ISO-8601.
    snapshot_date TEXT    NOT NULL CHECK (date(snapshot_date) IS snapshot_date),
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
