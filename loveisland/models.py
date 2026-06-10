"""Data shapes that flow through the pipeline.

Two records matter:

* ``RawItem``        — what a collector returns straight from a source API.
* ``NormalizedRecord`` — the cleaned, source-agnostic row we store in the
  database (sentiment fields start empty and are filled in later by scoring).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawItem:
    """A single piece of commentary, exactly as a collector fetched it."""

    source: str                       # "youtube" | "news" | "reddit" | "x"
    external_id: str                  # the source's own id for this item
    text: str                         # the comment / headline / article text
    created_at: datetime              # when it was posted (timezone-aware)
    url: str                          # link back to the item
    author_id: Optional[str] = None   # raw author id — hashed before storage
    raw: dict = field(default_factory=dict)  # any extra source-specific fields


@dataclass
class NormalizedRecord:
    """A cleaned row ready for the database. One per collected item."""

    source: str
    external_id: str
    show: str
    season: int
    text: str
    created_at: str                   # ISO-8601 UTC string
    collected_at: str                 # ISO-8601 UTC string
    url: str
    author_hash: str                  # sha256(author_id + salt) — never raw

    episode: Optional[int] = None
    entity: Optional[str] = None       # coarse contestant/couple tag
    entity_type: Optional[str] = None  # "contestant" | "couple"
    lang: Optional[str] = None
    text_hash: Optional[str] = None    # for de-duping + sentiment caching

    # Filled in later by the sentiment module:
    sentiment_label: Optional[str] = None   # positive | neutral | negative | mixed
    sentiment_score: Optional[float] = None # -1.0 .. +1.0
