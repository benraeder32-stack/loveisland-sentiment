"""Database access: connect, create tables, insert records, run queries.

STATUS: placeholder. Real implementation lands in the "store + schema" step.
The function signatures are defined here so other modules can import them.
"""

from __future__ import annotations

from pathlib import Path

from ..config import ROOT
from ..models import NormalizedRecord

DB_PATH = ROOT / "data" / "loveisland.db"


def init_db(db_path: Path = DB_PATH) -> None:
    """Create the database file and tables from schema.sql (idempotent)."""
    raise NotImplementedError("init_db is implemented in the store + schema step.")


def upsert_items(records: list[NormalizedRecord], db_path: Path = DB_PATH) -> int:
    """Insert new records, skip duplicates. Returns count inserted."""
    raise NotImplementedError("upsert_items is implemented in the store + schema step.")
