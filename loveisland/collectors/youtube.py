"""YouTube Data API collector — comments on recap / reaction videos.

How it works:
  1. Find recent videos using the search terms (and any channels) in config.
  2. For each video, page through its top-level comments newest-first.
  3. Stop paging a video once comments are older than ``since`` (saves quota).

Privacy: we keep the commenter's channel *id* only to hash it later — the
display name is never stored.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .base import Collector
from ..config import get_secret
from ..models import RawItem


def _parse_published(value: str) -> datetime:
    """Parse YouTube's RFC-3339 timestamp (e.g. 2026-06-08T20:00:00Z)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class YouTubeCollector(Collector):
    name = "youtube"

    def fetch(self, since: datetime) -> list[RawItem]:
        # Imported here so the rest of the app works even before this package
        # is installed, and so --help never needs the dependency.
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError

        api_key = get_secret("YOUTUBE_API_KEY", required=True)
        cfg = self.config.get("youtube", {}) or {}
        max_videos = int(cfg.get("max_videos", 15))
        max_comments = int(cfg.get("max_comments_per_video", 200))
        search_terms = cfg.get("search_terms", []) or []
        channels = cfg.get("channels", []) or []

        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        youtube = build("youtube", "v3", developerKey=api_key, cache_discovery=False)

        video_ids = self._find_videos(youtube, search_terms, channels, max_videos)

        items: list[RawItem] = []
        for vid in video_ids:
            try:
                items.extend(self._fetch_comments(youtube, vid, since, max_comments))
            except HttpError as exc:
                # Most commonly: comments are disabled on this video → skip it.
                print(f"    (skipped video {vid}: {getattr(exc, 'reason', exc)})")
        return items

    # ── helpers ─────────────────────────────────────────────────────────

    def _find_videos(self, youtube, search_terms, channels, max_videos) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()

        def add_search(**params):
            if len(ids) >= max_videos:
                return
            resp = youtube.search().list(
                part="id", type="video", order="date",
                maxResults=min(50, max_videos), **params,
            ).execute()
            for item in resp.get("items", []):
                vid = item["id"].get("videoId")
                if vid and vid not in seen:
                    seen.add(vid)
                    ids.append(vid)

        for term in search_terms:
            add_search(q=term)
        for channel_id in channels:
            add_search(channelId=channel_id)
        return ids[:max_videos]

    def _fetch_comments(self, youtube, video_id, since, max_comments) -> list[RawItem]:
        out: list[RawItem] = []
        page_token = None
        while len(out) < max_comments:
            resp = youtube.commentThreads().list(
                part="snippet", videoId=video_id, maxResults=100,
                order="time", textFormat="plainText", pageToken=page_token,
            ).execute()

            reached_old = False
            for thread in resp.get("items", []):
                top = thread["snippet"]["topLevelComment"]
                sn = top["snippet"]
                published = _parse_published(sn["publishedAt"])
                if published < since:
                    reached_old = True  # newest-first, so the rest are older too
                    break
                out.append(
                    RawItem(
                        source="youtube",
                        external_id=top["id"],
                        text=sn.get("textOriginal", ""),
                        created_at=published,
                        url=f"https://www.youtube.com/watch?v={video_id}&lc={top['id']}",
                        author_id=sn.get("authorChannelId", {}).get("value"),
                        raw={"video_id": video_id, "like_count": sn.get("likeCount", 0)},
                    )
                )
                if len(out) >= max_comments:
                    break

            page_token = resp.get("nextPageToken")
            if reached_old or not page_token:
                break
        return out
