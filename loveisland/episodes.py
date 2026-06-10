"""Tag a timestamp with the episode it falls under.

An episode "owns" comments posted between its air time and ``window_hours``
afterward (configured per episode in config.yaml). A comment outside every
window is left untagged (episode = None).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import Config


def _parse_air_date(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 air date; return timezone-aware UTC datetime."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EpisodeTagger:
    def __init__(self, config: Config):
        self._windows: list[tuple[datetime, datetime, int]] = []
        for ep in config.get("episodes", []) or []:
            air = _parse_air_date(ep.get("air_date", ""))
            if air is None:
                continue
            window = int(ep.get("window_hours", 48))
            self._windows.append((air, air + timedelta(hours=window), int(ep["number"])))

    def tag(self, created_at: datetime) -> Optional[int]:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        created_at = created_at.astimezone(timezone.utc)
        for start, end, number in self._windows:
            if start <= created_at <= end:
                return number
        return None
