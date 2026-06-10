"""Orchestration: turn collectors + scorer + store into the high-level
``collect`` / ``score`` / ``run`` actions the CLI exposes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .collectors.news_gdelt import GdeltNewsCollector
from .collectors.youtube import YouTubeCollector
from .config import Config
from .normalize import normalize_items
from .store import db

# Source name → collector class. v1 sources are added as they are built.
SOURCES: dict[str, type] = {
    "youtube": YouTubeCollector,
    "news": GdeltNewsCollector,
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
    raise NotImplementedError(
        "score() is wired up in the sentiment module step."
    )


def run(config: Config, since: datetime, sources: Optional[list[str]] = None) -> tuple[int, int]:
    """collect() then score(). Returns (items_added, items_scored)."""
    raise NotImplementedError(
        "run() is wired up in the 'wire run' step (after sentiment)."
    )
