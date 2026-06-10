"""GDELT news collector — news coverage of the show (free, no API key).

STATUS: placeholder. The real implementation lands in the "GDELT news
collector" step.
"""

from __future__ import annotations

from datetime import datetime

from .base import Collector
from ..models import RawItem


class GdeltNewsCollector(Collector):
    name = "news"

    def fetch(self, since: datetime) -> list[RawItem]:
        raise NotImplementedError(
            "GdeltNewsCollector.fetch is implemented in the GDELT news step."
        )
