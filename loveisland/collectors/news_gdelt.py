"""GDELT news collector — news coverage of the show (free, no API key).

Uses the GDELT DOC 2.0 API (https://api.gdeltproject.org/api/v2/doc/doc),
which returns recent news articles matching a query. We score the article
*headline* (GDELT exposes the title, not full body).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import Collector
from ..models import RawItem

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _build_query(terms: list[str]) -> str:
    """Combine terms into a GDELT query, e.g. ("Love Island USA" OR "LoveIslandUSA")."""
    phrases = [f'"{t}"' if " " in t else t for t in terms if t]
    if not phrases:
        return '"Love Island USA"'
    joined = " OR ".join(phrases)
    return f"({joined})" if len(phrases) > 1 else joined


def _parse_seendate(value: str) -> datetime:
    """Parse GDELT's seendate (e.g. 20260608T120000Z or 20260608120000)."""
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


class GdeltNewsCollector(Collector):
    name = "news"

    def _request_json(self, params: dict, retries: int = 3) -> dict | None:
        """GET the GDELT API, retrying on its 5-second rate limit. None on failure."""
        import time

        import requests  # imported here so --help never needs the dependency

        for attempt in range(retries):
            resp = requests.get(GDELT_ENDPOINT, params=params, timeout=30)
            body = resp.text.strip()
            rate_limited = resp.status_code == 429 or body.startswith("Please limit")
            if rate_limited:
                if attempt < retries - 1:
                    time.sleep(6)  # honor "one request every 5 seconds"
                    continue
                print("    (GDELT rate-limited; will catch up on the next run)")
                return None
            if resp.status_code != 200 or not body:
                print(f"    (GDELT returned status {resp.status_code}; skipping)")
                return None
            try:
                return resp.json()
            except ValueError:
                print(f"    (GDELT non-JSON response: {body[:120]})")
                return None
        return None

    def fetch(self, since: datetime) -> list[RawItem]:
        cfg = self.config.get("gdelt", {}) or {}
        max_records = int(cfg.get("max_records", 100))
        query = _build_query(cfg.get("query_terms", []) or [])

        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": min(250, max_records),
            "sort": "DateDesc",
            "startdatetime": since.strftime("%Y%m%d%H%M%S"),
            "enddatetime": now.strftime("%Y%m%d%H%M%S"),
        }

        data = self._request_json(params)
        if data is None:
            return []

        items: list[RawItem] = []
        seen: set[str] = set()
        for art in data.get("articles", []):
            url = art.get("url")
            title = (art.get("title") or "").strip()
            if not url or not title or url in seen:
                continue
            seen.add(url)
            items.append(
                RawItem(
                    source="news",
                    external_id=url,
                    text=title,
                    created_at=_parse_seendate(art.get("seendate", "")),
                    url=url,
                    author_id=None,  # articles have no per-user author
                    raw={
                        "domain": art.get("domain"),
                        "language": art.get("language"),
                        "country": art.get("sourcecountry"),
                    },
                )
            )
        return items
