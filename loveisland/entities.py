"""Config-driven entity tagging.

Reads the contestant/couple roster from config.yaml and tags a piece of text
with the contestant or couple it most likely refers to, using the canonical
names plus any aliases/nicknames.

This is a coarse, first-pass tag stored on every record. The sentiment module
later produces finer, per-entity "aspect" tags via the LLM.
"""

from __future__ import annotations

import re
from typing import Optional

from .config import Config


class EntityTagger:
    """Precompiles name/alias patterns from config for fast matching."""

    def __init__(self, config: Config):
        entities = config.get("entities", {}) or {}
        # Each pattern entry: (compiled_regex, canonical_name, entity_type)
        self._patterns: list[tuple[re.Pattern, str, str]] = []

        for couple in entities.get("couples", []) or []:
            names = [couple.get("canonical", "")]
            names += couple.get("aliases", []) or []
            names += couple.get("members", []) or []
            self._add(names, couple.get("canonical", ""), "couple")

        for person in entities.get("contestants", []) or []:
            names = [person.get("canonical", "")]
            names += person.get("aliases", []) or []
            self._add(names, person.get("canonical", ""), "contestant")

    def _add(self, names: list[str], canonical: str, entity_type: str) -> None:
        terms = [re.escape(n.strip()) for n in names if n and n.strip()]
        if not terms or not canonical:
            return
        pattern = re.compile(r"\b(" + "|".join(terms) + r")\b", re.IGNORECASE)
        self._patterns.append((pattern, canonical, entity_type))

    def tag(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Return (entity, entity_type) for the first match, else (None, None).

        Couples are checked before individuals so a ship-name wins over a
        single member's name.
        """
        if not text:
            return None, None
        for pattern, canonical, entity_type in self._patterns:
            if pattern.search(text):
                return canonical, entity_type
        return None, None
