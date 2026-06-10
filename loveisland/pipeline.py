"""Orchestration: turn collectors + scorer + store into the high-level
``collect`` / ``score`` / ``run`` actions the CLI exposes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .collectors.bluesky import BlueskyCollector
from .collectors.news_gdelt import GdeltNewsCollector
from .collectors.tumblr import TumblrCollector
from .collectors.youtube import YouTubeCollector
from .config import Config
from .normalize import normalize_items
from .store import db

# Source name → collector class. All are free, read-only, sanctioned APIs.
SOURCES: dict[str, type] = {
    "youtube": YouTubeCollector,
    "news": GdeltNewsCollector,
    "bluesky": BlueskyCollector,
    "tumblr": TumblrCollector,
}


def collect(config: Config, since: datetime, sources: Optional[list[str]] = None) -> int:
    """Run the selected collectors, normalize, and store. Returns items added."""
    selected = sources or list(SOURCES.keys())
    total = 0
    for name in selected:
        collector_cls = SOURCES.get(name)
        if collector_cls is None:
            print(f"  • {name}: not available yet — skipping.")
            continue
        collector = collector_cls(config)
        try:
            raw = collector.fetch(since)
        except NotImplementedError:
            print(f"  • {name}: collector not built yet — skipping.")
            continue
        records = normalize_items(raw, config)
        added = db.upsert_items(records)
        print(f"  • {name}: fetched {len(raw)}, stored {added} new.")
        total += added

    db.set_meta("last_collect", datetime.now().astimezone().isoformat())
    return total


def score(config: Config, limit: Optional[int] = None, model: Optional[str] = None) -> int:
    """Score any unscored stored items. Returns items scored."""
    from .sentiment.scorer import score_unscored  # imported lazily (needs anthropic)
    return score_unscored(config, limit, model)


def run(config: Config, since: datetime, sources: Optional[list[str]] = None) -> tuple[int, int]:
    """collect() then score(). Returns (items_added, items_scored)."""
    added = collect(config, since, sources)
    scored = score(config)
    return added, scored
