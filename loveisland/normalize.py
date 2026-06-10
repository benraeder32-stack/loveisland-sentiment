"""Turn raw items from any collector into clean database records.

This is the single place where source-specific data becomes a uniform
``NormalizedRecord``: author IDs are hashed (never stored raw), text is hashed
for de-duping/caching, and the entity + episode tags are applied.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .config import Config, get_secret
from .entities import EntityTagger
from .episodes import EpisodeTagger
from .models import NormalizedRecord, RawItem

_DEFAULT_SALT = "loveisland-sentiment"


def _hash_author(author_id: str | None) -> str:
    """Irreversibly hash an author id with a salt. Empty id -> 'anonymous'."""
    if not author_id:
        return "anonymous"
    salt = get_secret("AUTHOR_HASH_SALT") or _DEFAULT_SALT
    return hashlib.sha256((salt + author_id).encode("utf-8")).hexdigest()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def normalize_items(raw_items: list[RawItem], config: Config) -> list[NormalizedRecord]:
    """Convert a list of RawItems into NormalizedRecords ready for storage."""
    entity_tagger = EntityTagger(config)
    episode_tagger = EpisodeTagger(config)
    collected_at = _iso_utc(datetime.now(timezone.utc))

    records: list[NormalizedRecord] = []
    for item in raw_items:
        text = (item.text or "").strip()
        if not text:
            continue  # skip empties
        entity, entity_type = entity_tagger.tag(text)
        records.append(
            NormalizedRecord(
                source=item.source,
                external_id=item.external_id,
                show=config.show,
                season=config.season,
                text=text,
                created_at=_iso_utc(item.created_at),
                collected_at=collected_at,
                url=item.url,
                author_hash=_hash_author(item.author_id),
                episode=episode_tagger.tag(item.created_at),
                entity=entity,
                entity_type=entity_type,
                text_hash=_hash_text(text),
            )
        )
    return records
