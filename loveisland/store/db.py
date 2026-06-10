"""Database access: connect, create tables, insert records, run queries.

All SQLite access for the project goes through this module, so swapping to
Postgres later means changing one file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from ..config import ROOT
from ..models import NormalizedRecord

DB_PATH = ROOT / "data" / "loveisland.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection, creating the data/ folder if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row            # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")  # enforce the aspects → items link
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the database file and all tables (safe to run repeatedly)."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(db_path) as conn:
        conn.executescript(schema)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply additive schema changes to an existing database (idempotent)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    if "like_count" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN like_count INTEGER DEFAULT 0")
    if "funny" not in cols:
        conn.execute("ALTER TABLE items ADD COLUMN funny REAL DEFAULT 0")


# ── Writing collected items ────────────────────────────────────────────

def upsert_items(records: list[NormalizedRecord], db_path: Path = DB_PATH) -> int:
    """Insert new records; skip any that already exist (same source+external_id).

    Returns the number actually inserted.
    """
    if not records:
        return 0
    inserted = 0
    with connect(db_path) as conn:
        for r in records:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO items (
                    source, external_id, show, season, episode,
                    entity, entity_type, author_hash, text, text_hash,
                    lang, url, like_count, created_at, collected_at,
                    sentiment_label, sentiment_score
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    r.source, r.external_id, r.show, r.season, r.episode,
                    r.entity, r.entity_type, r.author_hash, r.text, r.text_hash,
                    r.lang, r.url, r.like_count, r.created_at, r.collected_at,
                    r.sentiment_label, r.sentiment_score,
                ),
            )
            inserted += cur.rowcount  # 1 if inserted, 0 if a duplicate was ignored
    return inserted


# ── Scoring support (used by the sentiment module) ─────────────────────

def fetch_unscored_items(limit: Optional[int] = None, db_path: Path = DB_PATH) -> list[sqlite3.Row]:
    """Return items that have no overall sentiment yet."""
    sql = "SELECT id, text, text_hash FROM items WHERE sentiment_label IS NULL ORDER BY id"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    with connect(db_path) as conn:
        return conn.execute(sql, params).fetchall()


def save_item_sentiment(item_id: int, label: str, score: float, funny: float = 0.0,
                        db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE items SET sentiment_label = ?, sentiment_score = ?, funny = ? WHERE id = ?",
            (label, score, funny, item_id),
        )


def replace_aspects(item_id: int, aspects: list[dict], db_path: Path = DB_PATH) -> None:
    """Set the per-entity aspect rows for an item (clears any existing ones)."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM aspects WHERE item_id = ?", (item_id,))
        conn.executemany(
            """
            INSERT INTO aspects (item_id, entity, entity_type, topic,
                                 sentiment_label, sentiment_score)
            VALUES (?,?,?,?,?,?)
            """,
            [
                (
                    item_id, a.get("entity"), a.get("entity_type"), a.get("topic"),
                    a.get("label"), a.get("score"),
                )
                for a in aspects
            ],
        )


# ── Sentiment cache (skip re-scoring identical text) ───────────────────

def cache_get(text_hash: str, db_path: Path = DB_PATH) -> Optional[str]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT result_json FROM sentiment_cache WHERE text_hash = ?", (text_hash,)
        ).fetchone()
    return row["result_json"] if row else None


def cache_put(text_hash: str, model: str, result_json: str, scored_at: str,
              db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sentiment_cache (text_hash, model, result_json, scored_at)
            VALUES (?,?,?,?)
            """,
            (text_hash, model, result_json, scored_at),
        )


# ── Small helpers ──────────────────────────────────────────────────────

def count_items(db_path: Path = DB_PATH) -> int:
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]


def set_meta(key: str, value: str, db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))


def get_meta(key: str, db_path: Path = DB_PATH) -> Optional[str]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
