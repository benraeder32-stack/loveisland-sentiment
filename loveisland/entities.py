"""Config-driven entity tagging.

Reads the contestant/couple roster from config.yaml and tags a piece of text
with the contestant or couple it most likely refers to.

Matching rules (couples are checked first):
  * A COUPLE matches when its ship-name/alias appears (e.g. "Zryce"), OR when
    *all* of its members are mentioned (nickname-aware, e.g. "Bea" → Beatriz).
  * Otherwise an individual CONTESTANT matches on their name or any alias.

This is a coarse, first-pass tag stored on every record. The sentiment module
later produces finer, per-entity "aspect" tags via the LLM.
"""

from __future__ import annotations

import re
from typing import Optional

from .config import Config


def _compile(names: list[str]) -> Optional[re.Pattern]:
    terms = [re.escape(n.strip()) for n in names if n and n.strip()]
    if not terms:
        return None
    return re.compile(r"\b(" + "|".join(terms) + r")\b", re.IGNORECASE)


class EntityTagger:
    def __init__(self, config: Config):
        entities = config.get("entities", {}) or {}

        # canonical (lowercased) -> [name + aliases], so couple members can be
        # matched by any of a person's names.
        self._names_by_person: dict[str, list[str]] = {}
        self._contestants: list[tuple[re.Pattern, str]] = []
        for person in entities.get("contestants", []) or []:
            canonical = (person.get("canonical") or "").strip()
            if not canonical:
                continue
            names = [canonical] + (person.get("aliases") or [])
            self._names_by_person[canonical.lower()] = names
            pattern = _compile(names)
            if pattern:
                self._contestants.append((pattern, canonical))

        # couple -> (canonical, alias/ship pattern, [per-member patterns])
        self._couples: list[tuple[str, Optional[re.Pattern], list[re.Pattern]]] = []
        for couple in entities.get("couples", []) or []:
            canonical = (couple.get("canonical") or "").strip()
            if not canonical:
                continue
            alias_pattern = _compile([canonical] + (couple.get("aliases") or []))
            member_patterns = []
            for member in couple.get("members") or []:
                names = self._names_by_person.get(member.strip().lower(), [member])
                pat = _compile(names)
                if pat:
                    member_patterns.append(pat)
            self._couples.append((canonical, alias_pattern, member_patterns))

    def tag(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Return (entity, entity_type), or (None, None) if nothing matches."""
        if not text:
            return None, None

        for canonical, alias_pattern, member_patterns in self._couples:
            if alias_pattern and alias_pattern.search(text):
                return canonical, "couple"
            if member_patterns and all(p.search(text) for p in member_patterns):
                return canonical, "couple"

        for pattern, canonical in self._contestants:
            if pattern.search(text):
                return canonical, "contestant"

        return None, None
