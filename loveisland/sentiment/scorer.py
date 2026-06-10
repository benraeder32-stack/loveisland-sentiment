"""Sends comments to the Anthropic API and records sentiment.

Design:
  * Batch comments (N per call) to cut overhead.
  * Force structured JSON output (one result per comment) so parsing is safe.
  * Cache every result by text hash, so re-runs never re-score (or re-bill)
    the same text.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from ..config import Config, get_secret
from ..store import db
from .rubric import build_system_prompt

DEFAULT_MODEL = "claude-haiku-4-5"

# Forces the model to return exactly one result object per comment, in order.
RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "overall": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string",
                                      "enum": ["positive", "neutral", "negative", "mixed"]},
                            "score": {"type": "number"},
                        },
                        "required": ["label", "score"],
                        "additionalProperties": False,
                    },
                    "funny": {"type": "number"},
                    "aspects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "entity": {"type": "string"},
                                "entity_type": {"type": "string",
                                                "enum": ["contestant", "couple"]},
                                "topic": {"type": "string",
                                          "enum": ["coupling", "drama", "game", "other"]},
                                "label": {"type": "string",
                                          "enum": ["positive", "neutral", "negative", "mixed"]},
                                "score": {"type": "number"},
                            },
                            "required": ["entity", "entity_type", "topic", "label", "score"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["overall", "funny", "aspects"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=get_secret("ANTHROPIC_API_KEY", required=True))


def score_batch(client, model: str, system_prompt: str, texts: list[str]) -> list[dict]:
    """Score one batch of comment texts. Returns a list of result dicts (in order)."""
    numbered = "\n".join(f"{i + 1}. {t[:1000]}" for i, t in enumerate(texts))
    user = (
        f"Score these {len(texts)} comments about the show. Return exactly one "
        f"result per comment, in the same order.\n\n{numbered}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=min(16000, 600 * len(texts) + 1000),
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": RESULT_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(text).get("results", [])


def roster_names(config: Config) -> set:
    """The exact canonical contestant + couple names from config.yaml."""
    ent = config.get("entities", {}) or {}
    names = {p.get("canonical") for p in (ent.get("contestants") or []) if p.get("canonical")}
    names |= {c.get("canonical") for c in (ent.get("couples") or []) if c.get("canonical")}
    return names


def score_unscored(config: Config, limit: Optional[int] = None,
                   model: Optional[str] = None) -> int:
    """Score every stored item that has no sentiment yet. Returns the count scored."""
    rows = db.fetch_unscored_items(limit)
    if not rows:
        return 0

    sentiment_cfg = config.get("sentiment", {}) or {}
    model = model or sentiment_cfg.get("model") or DEFAULT_MODEL
    batch_size = int(sentiment_cfg.get("batch_size", 20))
    system_prompt = build_system_prompt(config)
    valid = roster_names(config)
    client = _client()
    now = datetime.now(timezone.utc).isoformat()

    scored = 0
    to_score = []
    # 1) Re-use any cached results for identical text (no API call, no charge).
    for row in rows:
        cached = db.cache_get(row["text_hash"])
        if cached:
            _apply(json.loads(cached), row["id"], valid)
            scored += 1
        else:
            to_score.append(row)

    # 2) Score the rest in batches.
    for start in range(0, len(to_score), batch_size):
        batch = to_score[start:start + batch_size]
        try:
            results = score_batch(client, model, system_prompt, [r["text"] for r in batch])
        except Exception as exc:  # network/parse/API error — leave for next run
            print(f"    (scoring batch failed: {exc}; will retry next run)")
            continue
        for row, result in zip(batch, results):
            _apply(result, row["id"], valid)
            db.cache_put(row["text_hash"], model, json.dumps(result), now)
            scored += 1
        print(f"    scored {min(start + batch_size, len(to_score))}/{len(to_score)} new")

    return scored


def _apply(result: dict, item_id: int, valid: Optional[set] = None) -> None:
    overall = result.get("overall", {}) or {}
    db.save_item_sentiment(
        item_id,
        overall.get("label", "neutral"),
        float(overall.get("score", 0.0)),
        float(result.get("funny", 0.0) or 0.0),
    )
    aspects = result.get("aspects", []) or []
    if valid is not None:  # keep only entities that are on the configured roster
        aspects = [a for a in aspects if a.get("entity") in valid]
    db.replace_aspects(item_id, aspects)
