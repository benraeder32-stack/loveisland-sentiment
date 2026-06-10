"""X / Twitter collector — via the official paid API.

STATUS: stubbed placeholder for later. X is a paid API, so this stays off for
v1. Implement ``fetch`` here if/when you add a paid X plan, using the official
API only (never scrape X web pages).
"""

from __future__ import annotations

from datetime import datetime

from .base import Collector
from ..config import get_secret
from ..models import RawItem


class XApiCollector(Collector):
    name = "x"

    def is_enabled(self) -> bool:
        return bool(get_secret("X_BEARER_TOKEN"))

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "X/Twitter collector is a paid-API placeholder for a later version."
        )
