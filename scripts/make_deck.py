#!/usr/bin/env python3
"""Generate the 'Group Chat Report' PowerPoint from the live database.

Re-run any time (e.g. after the 6pm pull) to refresh every number and quote:
    .venv/bin/python scripts/make_deck.py
Output: outputs/love_island_report.pptx
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from loveisland.store import db

# ── Palette (Love Island after-dark) ──────────────────────────────────
BG    = RGBColor(0x11, 0x0D, 0x22)
CARD  = RGBColor(0x1E, 0x16, 0x34)
CARD2 = RGBColor(0x2A, 0x1F, 0x47)
PINK  = RGBColor(0xFF, 0x2E, 0x88)
GOLD  = RGBColor(0xFF, 0xC9, 0x3C)
WHITE = RGBColor(0xF5, 0xF2, 0xFA)
MUTE  = RGBColor(0x9E, 0x8F, 0xB8)
GREEN = RGBColor(0x36, 0xE2, 0x7B)
RED   = RGBColor(0xFF, 0x5C, 0x5C)
HEAD, BODY = "Arial Black", "Arial"

EMU_W, EMU_H = Inches(13.333), Inches(7.5)


# ── Data ───────────────────────────────────────────────────────────────

def fetch():
    c = db.connect()
    q = lambda s, *p: c.execute(s, p).fetchall()
    d = {}
    d["total"] = c.execute("SELECT COUNT(*) FROM items WHERE sentiment_label IS NOT NULL").fetchone()[0]
    d["avg"] = c.execute("SELECT AVG(sentiment_score) FROM items WHERE sentiment_score IS NOT NULL").fetchone()[0] or 0.0
    d["sources"] = q("SELECT source, COUNT(*) n FROM items GROUP BY source ORDER BY n DESC")
    d["span"] = c.execute("SELECT MIN(created_at), MAX(created_at) FROM items").fetchone()
    d["pos"] = c.execute("SELECT AVG(sentiment_score>=0.15) FROM items WHERE sentiment_score IS NOT NULL").fetchone()[0] or 0
    d["neg"] = c.execute("SELECT AVG(sentiment_score<=-0.15) FROM items WHERE sentiment_score IS NOT NULL").fetchone()[0] or 0
    d["discussed"] = q("SELECT entity, COUNT(*) n FROM aspects WHERE entity_type='contestant' GROUP BY entity ORDER BY n DESC LIMIT 6")
    d["faves"] = q("SELECT entity, COUNT(*) n, AVG(sentiment_score) a FROM aspects WHERE entity_type='contestant' GROUP BY entity HAVING n>=5 ORDER BY a DESC LIMIT 5")
    d["villains"] = q("SELECT entity, COUNT(*) n, AVG(sentiment_score) a FROM aspects WHERE entity_type='contestant' GROUP BY entity HAVING n>=5 ORDER BY a ASC LIMIT 5")
    d["couples"] = q("SELECT entity, COUNT(*) n, AVG(sentiment_score) a FROM aspects WHERE entity_type='couple' GROUP BY entity HAVING n>=3 ORDER BY a DESC")
    d["burns"] = q("SELECT entity, text, source FROM items WHERE funny>=0.55 AND sentiment_score<=-0.2 ORDER BY funny DESC, like_count DESC LIMIT 5")
    d["funny"] = q("SELECT entity, text, source FROM items WHERE funny>=0.6 ORDER BY funny DESC, like_count DESC LIMIT 4")
    return d


def clean(t, n=155):
    t = re.sub(r"\s+", " ", (t or "").strip())
    return (t[:n].rstrip() + "…") if len(t) > n else t


# ── Slide helpers ───────────────────────────────────────────────────────

def slide(prs, bg=BG):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, EMU_W, EMU_H)
    r.fill.solid(); r.fill.fore_color.rgb = bg; r.line.fill.background()
    r.shadow.inherit = False
    return s


def text(s, l, t, w, h, runs, size, color, *, font=BODY, bold=True, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.0):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lines = runs if isinstance(runs, list) else [(runs, color, size, bold, font)]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = spacing
        txt, col, sz, bd, fn = (ln + (None,) * 5)[:5]
        col = col or color; sz = sz or size; bd = bold if bd is None else bd; fn = fn or font
        r = p.add_run(); r.text = txt
        r.font.size = Pt(sz); r.font.bold = bd; r.font.name = fn; r.font.color.rgb = col
    return tb


def card(s, l, t, w, h, fill=CARD, line=None):
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line: sh.line.color.rgb = line; sh.line.width = Pt(1.5)
    else: sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def bar(s, l, t, w, h, frac, color):
    track = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(w), Inches(h))
    track.fill.solid(); track.fill.fore_color.rgb = CARD2; track.line.fill.background(); track.shadow.inherit = False
    fw = max(0.12, w * max(0.04, min(1.0, frac)))
    fill = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(l), Inches(t), Inches(fw), Inches(h))
    fill.fill.solid(); fill.fill.fore_color.rgb = color; fill.line.fill.background(); fill.shadow.inherit = False


def title(s, kicker, ttl, ttl_color=WHITE):
    text(s, 0.62, 0.42, 12.1, 0.4, kicker.upper(), 15, GOLD, font=BODY)
    text(s, 0.6, 0.74, 12.1, 1.0, ttl.upper(), 38, ttl_color, font=HEAD)


def ranking(s, rows, top, color_fn, denom=0.4, mention_note=True):
    for i, (name, n, a) in enumerate(rows):
        y = top + i * 0.86
        text(s, 0.7, y, 3.6, 0.5, name, 25, WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
        if mention_note:
            text(s, 0.7, y + 0.5, 3.6, 0.3, f"{n:,} mentions", 11, MUTE)
        col = color_fn(a)
        bar(s, 4.5, y + 0.12, 6.7, 0.4, abs(a) / denom, col)
        text(s, 11.35, y, 1.7, 0.6, f"{a:+.2f}", 22, col, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)


def quote_card(s, l, t, w, h, quote, src):
    card(s, l, t, w, h, CARD)
    text(s, l + 0.3, t + 0.16, w - 0.6, 0.45, "“", 38, PINK, font=HEAD, anchor=MSO_ANCHOR.TOP)
    text(s, l + 0.32, t + 0.58, w - 0.64, h - 1.05, clean(quote, 125), 14, WHITE, bold=False, spacing=1.04)
    text(s, l + 0.32, t + h - 0.42, w - 0.64, 0.3, f"via {src}", 11, GOLD)


# ── Build ────────────────────────────────────────────────────────────────

def build(d):
    prs = Presentation(); prs.slide_width = EMU_W; prs.slide_height = EMU_H
    fave_c = lambda a: GREEN if a >= 0 else RED
    span_lo = (d["span"][0] or "")[:10]; span_hi = (d["span"][1] or "")[:10]

    # 1 — Title
    s = slide(prs)
    card(s, 0, 0, 13.333, 0.16, PINK)
    text(s, 0.9, 1.7, 11.5, 0.5, "LOVE ISLAND USA · SEASON 8", 18, GOLD, font=BODY, align=PP_ALIGN.CENTER)
    text(s, 0.5, 2.35, 12.3, 1.1, "THE GROUP CHAT REPORT", 47, WHITE, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, 1.2, 3.65, 10.9, 0.7, "What the internet REALLY thinks before tonight's episode 🌴🍷",
         22, PINK, font=BODY, align=PP_ALIGN.CENTER)
    text(s, 1.2, 5.25, 10.9, 0.6, f"{d['total']:,} comments read across YouTube · Bluesky · Tumblr · News",
         16, WHITE, bold=False, align=PP_ALIGN.CENTER)
    text(s, 1.2, 5.72, 10.9, 0.5, "so you don't have to.", 14, MUTE, bold=False, align=PP_ALIGN.CENTER)

    # 2 — Vibe check
    s = slide(prs)
    title(s, "the state of the villa", "The Vibe Check")
    stats = [(f"{d['total']:,}", "comments analyzed"),
             (str(len(d["sources"])), "platforms"),
             (f"{int(round((datetime.fromisoformat(d['span'][1]).date() - datetime.fromisoformat(d['span'][0]).date()).days))}d", "of season covered")]
    for i, (big, lab) in enumerate(stats):
        x = 0.7 + i * 4.15
        card(s, x, 2.0, 3.8, 1.7, CARD)
        text(s, x, 2.2, 3.8, 0.95, big, 50, GOLD, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x, 3.15, 3.8, 0.4, lab, 14, MUTE, align=PP_ALIGN.CENTER)
    mood = "DIVIDED 😬" if abs(d["avg"]) < 0.1 else ("ROUGH 🔥" if d["avg"] < 0 else "GLOWING ☀️")
    card(s, 0.7, 4.1, 11.95, 2.55, CARD2)
    text(s, 1.1, 4.4, 11.2, 0.5, "OVERALL MOOD", 15, MUTE)
    text(s, 1.1, 4.78, 11.2, 1.0, mood, 46, PINK, font=HEAD)
    text(s, 1.1, 5.85, 11.2, 0.7,
         f"{d['pos']*100:.0f}% in their feels good  ·  {d['neg']*100:.0f}% absolutely seething  ·  "
         "the group chat is FEASTING.", 17, WHITE, bold=False)

    # 3 — Main characters
    s = slide(prs)
    top_name = d["discussed"][0][0]
    title(s, "who the internet can't shut up about", "Main Characters")
    text(s, 0.62, 1.72, 12.1, 0.5, f"{top_name} is living rent-free in everyone's head.", 16, GOLD, bold=False)
    mx = max(n for _, n in d["discussed"]) or 1
    for i, (name, n) in enumerate(d["discussed"]):
        y = 2.35 + i * 0.78
        text(s, 0.7, y, 3.4, 0.5, name, 23, WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
        bar(s, 4.3, y + 0.1, 6.9, 0.38, n / mx, PINK)
        text(s, 11.35, y, 1.8, 0.5, f"{n:,}", 20, GOLD, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)

    # 4 — Fan favorites
    s = slide(prs)
    title(s, "the ones who can do no wrong", "Fan Favorites 💖", GREEN)
    text(s, 0.62, 1.72, 12.1, 0.5, f"{d['faves'][0][0]} is the people's princess.", 16, GOLD, bold=False)
    ranking(s, d["faves"], 2.4, lambda a: GREEN)

    # 5 — Villains
    s = slide(prs)
    worst = d["villains"][0][0]
    title(s, "public enemies", "Getting Cooked 🔥", RED)
    text(s, 0.62, 1.72, 12.1, 0.5, f"{worst} is public enemy #1. The villa wants blood.", 16, GOLD, bold=False)
    ranking(s, d["villains"], 2.4, lambda a: RED)

    # 6 — Couples
    s = slide(prs)
    best = d["couples"][0]; worst_c = d["couples"][-1]
    title(s, "endgame or endgame-over", "Couple Chemistry 💑")
    text(s, 0.62, 1.72, 12.1, 0.6,
         f"The people's verdict: {best[0]} 💚 is winning, {worst_c[0]} 💔 is doomed.", 15, GOLD, bold=False)
    cx, cw = 6.7, 4.7  # zero-center at cx, half-width cw
    for i, (name, n, a) in enumerate(d["couples"]):
        y = 2.45 + i * 0.5
        col = GREEN if a >= 0 else RED
        text(s, 0.7, y - 0.02, 4.4, 0.4, name, 15, WHITE, font=BODY, anchor=MSO_ANCHOR.MIDDLE)
        frac = max(0.03, min(1.0, abs(a) / 0.45)) * cw
        if a >= 0:
            bar(s, cx, y + 0.05, frac, 0.28, 1.0, col)
        else:
            b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(cx - frac), Inches(y + 0.05), Inches(frac), Inches(0.28))
            b.fill.solid(); b.fill.fore_color.rgb = col; b.line.fill.background(); b.shadow.inherit = False
        text(s, cx + cw + 0.15, y - 0.02, 1.0, 0.4, f"{a:+.2f}", 13, col, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    # zero line
    zl = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(cx - 0.01), Inches(2.4), Inches(0.02), Inches(len(d["couples"]) * 0.5 + 0.1))
    zl.fill.solid(); zl.fill.fore_color.rgb = MUTE; zl.line.fill.background(); zl.shadow.inherit = False

    # 7 — Burn book
    s = slide(prs)
    title(s, "the most savage takes we found", "The Burn Book 😈")
    pos = [(0.7, 2.0), (6.95, 2.0), (0.7, 4.35), (6.95, 4.35)]
    for (l, t), (who, q, src) in zip(pos, d["burns"][:4]):
        quote_card(s, l, t, 5.65, 2.1, q, src)

    # 8 — What to watch
    s = slide(prs)
    title(s, "storylines the data says to watch", "What To Watch Tonight 📺")
    blocks = [
        ("🎯 The Melanie Pile-On", f"She's the most-talked-about islander by a mile and the fans are NOT kind. Every move gets clipped."),
        ("💘 The Forbidden Ship", f"Fans are rooting for Sol & Sincere over his actual couple Melanie & Sincere. Triangle's about to blow."),
        ("🐍 Gabriel, Menace at Large", "Kissing everyone, trusted by no one. One of the lowest-rated men in the villa."),
        ("👬 Zryce Nation", "The internet has decided Zach & Bryce are the real love story. Let them cook."),
    ]
    for i, (h, b) in enumerate(blocks):
        x = 0.7 + (i % 2) * 6.25
        y = 2.05 + (i // 2) * 2.35
        card(s, x, y, 5.7, 2.05, CARD)
        text(s, x + 0.3, y + 0.25, 5.1, 0.6, h, 19, PINK, font=HEAD)
        text(s, x + 0.3, y + 0.95, 5.1, 1.0, b, 14, WHITE, bold=False, spacing=1.05)

    # 9 — Verdict
    s = slide(prs)
    card(s, 0, 0, 13.333, 0.16, PINK)
    text(s, 0.7, 1.3, 11.9, 0.9, "THE VERDICT", 50, WHITE, font=HEAD, align=PP_ALIGN.CENTER)
    cards = [("💖 FAN FAVORITE", d["faves"][0][0], GREEN),
             ("🔥 MOST BOOED", worst, RED),
             ("💑 SHIP THE PEOPLE DEMAND", best[0], PINK)]
    for i, (lab, val, col) in enumerate(cards):
        x = 0.7 + i * 4.15
        card(s, x, 2.7, 3.8, 1.9, CARD)
        text(s, x + 0.2, 2.95, 3.4, 0.4, lab, 13, MUTE, align=PP_ALIGN.CENTER)
        text(s, x + 0.2, 3.45, 3.4, 1.0, val, 30, col, font=HEAD, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.0, 5.2, 11.3, 0.7, "Now stop reading and go watch. 🍷📺", 26, GOLD, font=HEAD, align=PP_ALIGN.CENTER)
    text(s, 1.0, 6.1, 11.3, 0.5, f"Data as of {span_hi} · {d['total']:,} comments · built by the group chat's resident data nerd",
         12, MUTE, bold=False, align=PP_ALIGN.CENTER)

    return prs


if __name__ == "__main__":
    data = fetch()
    out = Path(__file__).resolve().parent.parent / "outputs" / "love_island_report.pptx"
    out.parent.mkdir(exist_ok=True)
    build(data).save(out)
    print(f"✅ Saved {out}  ({data['total']:,} comments)")
