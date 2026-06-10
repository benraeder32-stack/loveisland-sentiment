-- ============================================================
--  Database schema for the Love Island sentiment tracker.
--
--  Designed for SQLite (v1) but kept portable so it can migrate
--  to Postgres later:
--    * timestamps are stored as ISO-8601 TEXT (UTC)
--    * scores are REAL (Postgres: DOUBLE PRECISION)
--    * ids are INTEGER PRIMARY KEY (Postgres: BIGSERIAL/IDENTITY)
-- ============================================================

-- One row per collected comment / headline / article.
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,   -- youtube | news | reddit | x
    external_id     TEXT    NOT NULL,   -- the source's own id
    show            TEXT    NOT NULL,
    season          INTEGER NOT NULL,
    episode         INTEGER,            -- nullable; tagged by air-date window
    entity          TEXT,               -- coarse contestant/couple tag (nullable)
    entity_type     TEXT,               -- contestant | couple
    author_hash     TEXT,               -- sha256(author_id + salt); never raw
    text            TEXT    NOT NULL,
    text_hash       TEXT    NOT NULL,   -- for de-dupe + sentiment caching
    lang            TEXT,
    url             TEXT,
    like_count      INTEGER DEFAULT 0,  -- engagement (e.g. YouTube likes)
    created_at      TEXT    NOT NULL,   -- when posted (ISO-8601 UTC)
    collected_at    TEXT    NOT NULL,   -- when we fetched it (ISO-8601 UTC)
    sentiment_label TEXT,               -- positive|neutral|negative|mixed (nullable)
    sentiment_score REAL,               -- -1.0 .. +1.0 (nullable)
    funny           REAL DEFAULT 0,     -- 0.0 .. 1.0 how funny/savage (LLM-rated)
    UNIQUE (source, external_id)        -- makes re-collection idempotent
);

CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source);
CREATE INDEX IF NOT EXISTS idx_items_episode   ON items(episode);
CREATE INDEX IF NOT EXISTS idx_items_entity    ON items(entity);
CREATE INDEX IF NOT EXISTS idx_items_created   ON items(created_at);
CREATE INDEX IF NOT EXISTS idx_items_text_hash ON items(text_hash);
CREATE INDEX IF NOT EXISTS idx_items_unscored  ON items(sentiment_label);

-- One row per (item, entity, topic) the LLM identifies — the fine-grained,
-- per-contestant / per-couple breakdown that powers the dashboard.
CREATE TABLE IF NOT EXISTS aspects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    entity          TEXT    NOT NULL,
    entity_type     TEXT,               -- contestant | couple
    topic           TEXT,               -- coupling | drama | game | other
    sentiment_label TEXT,
    sentiment_score REAL
);

CREATE INDEX IF NOT EXISTS idx_aspects_item   ON aspects(item_id);
CREATE INDEX IF NOT EXISTS idx_aspects_entity ON aspects(entity);
CREATE INDEX IF NOT EXISTS idx_aspects_topic  ON aspects(topic);

-- Caches a sentiment result by the hash of the text, so identical text is
-- never scored (or billed) twice — even across re-runs.
CREATE TABLE IF NOT EXISTS sentiment_cache (
    text_hash   TEXT PRIMARY KEY,
    model       TEXT NOT NULL,
    result_json TEXT NOT NULL,         -- the raw model result for this text
    scored_at   TEXT NOT NULL
);

-- Small key/value table for bookkeeping (e.g. last successful run time).
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
