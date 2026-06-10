"""The scoring rubric (prompt) sent to the model.

This is the heart of the sentiment quality. It must handle the messy reality of
reality-TV social commentary: sarcasm, nicknames, and spoilers.

``build_system_prompt`` injects the current roster so the model can resolve
nicknames to canonical names and only tag entities that exist this season.
"""

from __future__ import annotations

from ..config import Config


SYSTEM_RUBRIC = """\
You score viewer sentiment about the reality show "Love Island USA".

For EACH numbered comment you receive, judge the commenter's attitude. Return
ONE result object per comment, in the same order, as strict JSON.

OVERALL sentiment (the commenter's net attitude in this comment):
  - label: one of "positive", "neutral", "negative", "mixed"
  - score: a number from -1.0 (very negative) to +1.0 (very positive)

ASPECTS (zero or more): who/what the comment is about and the feeling toward
each. For every contestant or couple clearly referenced, emit:
  - entity: the CANONICAL name from the roster below (resolve nicknames first)
  - entity_type: "contestant" or "couple"
  - topic: one of "coupling", "drama", "game", "other"
  - label: "positive" | "neutral" | "negative" | "mixed"
  - score: -1.0 .. +1.0

CRITICAL READING RULES:
1. SARCASM & irony: judge the INTENDED meaning, not the literal words.
   "oh GREAT, another meltdown 🙄" is negative despite the word "great".
   Emoji, "lol", "💀", ALL CAPS, and "...sure." often flip literal polarity.
2. NICKNAMES: fans rarely use full names. Map nicknames, first names, handles,
   and ship-names to the canonical roster entry. If a reference is ambiguous or
   not in the roster, do NOT invent an entity — omit it.
3. SPOILERS / reported events: a comment may describe what happened on the show
   ("she dumped him at the recoupling"). Score the COMMENTER'S stance, not the
   event. Reporting a breakup neutrally is neutral, not negative.
4. Quoted or referenced text (e.g. quoting another user to disagree) is not the
   commenter's own view — weight the commenter's framing.
5. Off-topic, spam, or content with no clear show sentiment: overall "neutral",
   score 0.0, empty aspects.

Output JSON only. No prose, no markdown fences.
"""


def build_system_prompt(config: Config) -> str:
    """Append the season's roster (canonical names + aliases) to the rubric."""
    entities = config.get("entities", {}) or {}
    lines: list[str] = ["", "ROSTER for this season (canonical name <- aliases):"]

    for person in entities.get("contestants", []) or []:
        canonical = person.get("canonical", "")
        aliases = ", ".join(person.get("aliases", []) or [])
        lines.append(f"  [contestant] {canonical}" + (f" <- {aliases}" if aliases else ""))

    for couple in entities.get("couples", []) or []:
        canonical = couple.get("canonical", "")
        aliases = ", ".join(couple.get("aliases", []) or [])
        members = ", ".join(couple.get("members", []) or [])
        extra = "; ".join(p for p in [f"members: {members}" if members else "",
                                      f"aliases: {aliases}" if aliases else ""] if p)
        lines.append(f"  [couple] {canonical}" + (f" ({extra})" if extra else ""))

    return SYSTEM_RUBRIC + "\n" + "\n".join(lines)
