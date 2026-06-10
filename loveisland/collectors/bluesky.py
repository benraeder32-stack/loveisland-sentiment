"""Bluesky collector — public posts via the atproto search API (free, read-only).

Auth: a handle + app password (env BLUESKY_HANDLE / BLUESKY_APP_PASSWORD) create
a session; `app.bsky.feed.searchPosts` then returns public posts. If no
credentials are set, this collector simply contributes nothing (v1 runs fine
without it).

Privacy: we keep the author's DID only to hash it — never a display name.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import Collector
from ..config import get_secret
from ..models import RawItem


def _parse_dt(value) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


class BlueskyCollector(Collector):
    name = "bluesky"

    def is_enabled(self) -> bool:
        return bool(get_secret("BLUESKY_HANDLE") and get_secret("BLUESKY_APP_PASSWORD"))

    def fetch(self, since: datetime) -> list[RawItem]:
        handle = get_secret("BLUESKY_HANDLE")
        app_pw = get_secret("BLUESKY_APP_PASSWORD")
        if not (handle and app_pw):
            print("    (bluesky: no credentials in .env — skipping)")
            return []

        from atproto import Client, models  # imported here so --help needs no dep

        cfg = self.config.get("bluesky", {}) or {}
        queries = cfg.get("queries", []) or []
        max_per_query = int(cfg.get("max_per_query", 200))
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        try:
            client = Client()
            client.login(handle, app_pw)
        except Exception as exc:
            print(f"    (bluesky: login failed: {exc})")
            return []

        items: list[RawItem] = []
        seen: set[str] = set()
        for query in queries:
            cursor = None
            fetched = 0
            while fetched < max_per_query:
                params = models.AppBskyFeedSearchPosts.Params(
                    q=query, limit=100, sort="latest", cursor=cursor
                )
                resp = self._search(client, params)
                if resp is None:
                    break
                posts = getattr(resp, "posts", None) or []
                if not posts:
                    break

                reached_old = False
                for post in posts:
                    uri = post.uri
                    if uri in seen:
                        continue
                    record = post.record
                    created = _parse_dt(getattr(record, "created_at", None))
                    if created < since:
                        reached_old = True
                        break
                    seen.add(uri)
                    author_handle = post.author.handle
                    rkey = uri.rsplit("/", 1)[-1]
                    items.append(
                        RawItem(
                            source="bluesky",
                            external_id=uri,
                            text=getattr(record, "text", "") or "",
                            created_at=created,
                            url=f"https://bsky.app/profile/{author_handle}/post/{rkey}",
                            author_id=post.author.did,
                            raw={"handle": author_handle},
                        )
                    )
                    fetched += 1
                    if fetched >= max_per_query:
                        break

                cursor = getattr(resp, "cursor", None)
                if reached_old or not cursor:
                    break
        return items

    def _search(self, client, params, retries: int = 3):
        import time
        for attempt in range(retries):
            try:
                return client.app.bsky.feed.search_posts(params)
            except Exception as exc:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))  # basic backoff
                    continue
                print(f"    (bluesky search failed: {exc})")
                return None
        return None
