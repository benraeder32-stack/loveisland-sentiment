"""Tumblr collector — public posts via the v2 /tagged endpoint (free, read-only).

Auth: a consumer (API) key only — public reads need no user OAuth.
Env: TUMBLR_API_KEY. If it's missing, this collector contributes nothing.

Privacy: we keep the blog name only to hash it.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

from .base import Collector
from ..config import get_secret
from ..models import RawItem

TUMBLR_TAGGED = "https://api.tumblr.com/v2/tagged"


def _strip_html(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


class TumblrCollector(Collector):
    name = "tumblr"

    def is_enabled(self) -> bool:
        return bool(get_secret("TUMBLR_API_KEY"))

    def fetch(self, since: datetime) -> list[RawItem]:
        api_key = get_secret("TUMBLR_API_KEY")
        if not api_key:
            print("    (tumblr: no TUMBLR_API_KEY in .env — skipping)")
            return []

        import requests

        cfg = self.config.get("tumblr", {}) or {}
        tags = cfg.get("tags", []) or []
        max_per_tag = int(cfg.get("max_per_tag", 200))
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        since_epoch = int(since.timestamp())

        items: list[RawItem] = []
        seen: set[str] = set()
        for tag in tags:
            before = None
            fetched = 0
            while fetched < max_per_tag:
                params = {"tag": tag, "api_key": api_key, "limit": 20}
                if before:
                    params["before"] = before
                data = self._get(requests, params)
                if data is None:
                    break
                posts = data.get("response", []) or []
                if not posts:
                    break

                reached_old = False
                oldest = None
                for post in posts:
                    ts = int(post.get("timestamp", 0))
                    oldest = ts if oldest is None else min(oldest, ts)
                    if ts < since_epoch:
                        reached_old = True
                        continue
                    pid = str(post.get("id_string") or post.get("id") or "")
                    if not pid or pid in seen:
                        continue
                    text = post.get("summary") or _strip_html(
                        post.get("body") or post.get("caption") or ""
                    )
                    if not text:
                        continue
                    seen.add(pid)
                    items.append(
                        RawItem(
                            source="tumblr",
                            external_id=pid,
                            text=text,
                            created_at=datetime.fromtimestamp(ts, tz=timezone.utc),
                            url=post.get("post_url", ""),
                            author_id=post.get("blog_name"),
                            raw={"type": post.get("type"), "tag": tag},
                        )
                    )
                    fetched += 1
                    if fetched >= max_per_tag:
                        break

                if reached_old or oldest is None:
                    break
                before = oldest - 1  # page backward in time
        return items

    def _get(self, requests, params, retries: int = 3):
        import time
        for attempt in range(retries):
            resp = requests.get(TUMBLR_TAGGED, params=params, timeout=30)
            if resp.status_code == 429:
                if attempt < retries - 1:
                    time.sleep(5 * (attempt + 1))  # basic backoff
                    continue
                print("    (tumblr rate-limited; will catch up next run)")
                return None
            if resp.status_code != 200:
                print(f"    (tumblr status {resp.status_code}; skipping)")
                return None
            try:
                return resp.json()
            except ValueError:
                return None
        return None
