"""Sends comments to the Anthropic API and records sentiment.

STATUS: placeholder. Real implementation lands in the "sentiment module" step:
batch comments, call the model with the rubric, cache results by text hash so
re-runs never re-score (or re-bill) the same text.
"""

from __future__ import annotations

from ..config import Config


def score_unscored(config: Config, limit: int | None = None, model: str | None = None) -> int:
    """Score any stored items that have no sentiment yet. Returns count scored."""
    raise NotImplementedError("Scoring is implemented in the sentiment module step.")
