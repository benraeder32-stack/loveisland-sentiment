"""The shared Collector interface.

Every source (YouTube, news, Reddit, X) is a class that implements ``fetch``.
Because they all look the same from the outside, the pipeline can loop over
them without caring which source is which.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..config import Config
from ..models import RawItem


class Collector(ABC):
    """Base class for all data-source collectors."""

    #: short source name, e.g. "youtube" — also stored on every record
    name: str = "base"

    def __init__(self, config: Config):
        self.config = config

    @abstractmethod
    def fetch(self, since: datetime) -> list[RawItem]:
        """Return commentary created at or after ``since``.

        Implementations must NOT raise on an empty result — return ``[]``.
        """
        raise NotImplementedError
