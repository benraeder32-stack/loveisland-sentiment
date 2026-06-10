"""Reddit collector — READ-ONLY, via the official Data API (PRAW).

STATUS: stubbed on purpose.

Your Reddit API access is approval-gated. Until it is granted, this collector
stays switched off and v1 runs fine without it. When access lands:

  1. Fill in REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT in .env
  2. Implement ``fetch`` below using PRAW in read-only mode.

Hard rules for this collector (do not change):
  * READ-ONLY: never post, comment, vote, message, or take any mod action.
  * No username/password — app-only ("script" app) credentials.
  * Only public subreddit content (see ``reddit.subreddits`` in config.yaml).
"""

from __future__ import annotations

from datetime import datetime

from .base import Collector
from ..config import get_secret
from ..models import RawItem


class RedditCollector(Collector):
    name = "reddit"

    def is_enabled(self) -> bool:
        """True only when Reddit credentials are present in the environment."""
        return bool(
            get_secret("REDDIT_CLIENT_ID")
            and get_secret("REDDIT_CLIENT_SECRET")
            and get_secret("REDDIT_USER_AGENT")
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "Reddit collector is stubbed until API access is approved. "
            "It will use PRAW in read-only mode once REDDIT_* keys are set."
        )
