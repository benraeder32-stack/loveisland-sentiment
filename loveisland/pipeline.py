"""Orchestration: turn collectors + scorer + store into the high-level
``collect`` / ``score`` / ``run`` actions the CLI exposes.

STATUS: placeholder wiring. The real orchestration is filled in across the
collector, sentiment, and "wire run" steps. Signatures are stable so the CLI
can call them today.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .config import Config


def collect(config: Config, since: datetime, sources: Optional[list[str]] = None) -> int:
    """Run the selected collectors, normalize, and store. Returns items added."""
    raise NotImplementedError(
        "collect() is wired up in the collector and 'wire run' steps."
    )


def score(config: Config, limit: Optional[int] = None, model: Optional[str] = None) -> int:
    """Score any unscored stored items. Returns items scored."""
    raise NotImplementedError(
        "score() is wired up in the sentiment module step."
    )


def run(config: Config, since: datetime, sources: Optional[list[str]] = None) -> tuple[int, int]:
    """collect() then score(). Returns (items_added, items_scored)."""
    raise NotImplementedError(
        "run() is wired up in the 'wire run' step."
    )
