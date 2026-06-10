"""YouTube Data API collector — comments on recap / reaction videos.

STATUS: placeholder. The real implementation lands in the "YouTube collector"
step. The class and interface are here so the rest of the project can already
refer to it.
"""

from __future__ import annotations

from datetime import datetime

from .base import Collector
from ..models import RawItem


class YouTubeCollector(Collector):
    name = "youtube"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "YouTubeCollector.fetch is implemented in the YouTube collector step."
        )
