"""Streamlit dashboard — answer-first, and built to make people laugh.

Layout (top to bottom):
  • Vibe check one-liner
  • Top-line cards: fan favorite / getting cooked / main character / most divisive
  • 🌡️ Drama-o-meter
  • 😂 Funniest comments
  • Sentiment over time
  • By contestant / couple
  • 🔍 Spotlight (per person/couple: topics, loved/dragged, funniest takes)
  • By source & volume

Only entities on the configured Season roster are shown anywhere.

Run with:  python -m loveisland serve
"""

from __future__ import annotations

import re

try:
    import altair as alt
    import pandas as pd
    import streamlit as st
except ImportError:  # installed in the dashboard step
    alt = pd = st = None

# Streamlit runs this file as a top-level script, so make the package importable.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from loveisland.config import load_config  # noqa: E402
from loveisland.store import db  # noqa: E402

EASTERN = "America/New_York"


# ── Data loading (pure functions, testable without Streamlit) ──────────

def load_items() -> "pd.DataFrame":
    with db.connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, source, episode, entity, entity_type, text, url, "
            "like_count, created_at, sentiment_label, sentiment_score FROM items",
            conn,
        )
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        df["created_et"] = df["created_at"].dt.tz_convert(EASTERN)
        df["laugh"] = [laugh_score(t, l) for t, l in zip(df["text"], df["like_count"])]
    return df


def load_aspects() -> "pd.DataFrame":
    with db.connect() as conn:
        return pd.read_sql_query(
            "SELECT a.entity, a.entity_type, a.topic, a.sentiment_label, "
            "a.sentiment_score, i.created_at FROM aspects a "
            "JOIN items i ON i.id = a.item_id",
            conn,
        )


def load_entity_comments(entity: str) -> "pd.DataFrame":
    with db.connect() as conn:
        df = pd.read_sql_query(
            "SELECT i.text, i.source, i.url, i.like_count, a.topic, "
            "a.sentiment_score AS score, a.sentiment_label AS label "
            "FROM aspects a JOIN items i ON i.id = a.item_id WHERE a.entity = ?",
            conn, params=(entity,),
        )
    if not df.empty:
        df["laugh"] = [laugh_score(t, l) for t, l in zip(df["text"], df["like_count"])]
    return df


# ── "Funny" detector — surfaces chuckle-worthy fan reactions ───────────

_LAUGH_EMOJI = "😂🤣💀😭🙃🤡💅😩🙈🫠😅🤪"
_LAUGH_WORDS = (
    "lmfaooo", "lmfao", "lmaooo", "lmao", "lol", "rofl", "deceased", "i'm dead", "im dead",
    "screaming", "crying", "sobbing", "weeping", "cackling", "cackle", "hollering", "wheezing",
    "i can't", "i cant", "not me", "not him", "not her", "not the", "the way", "bestie",
    "plsss", "unserious", "chaotic", "icon", "ate that", "slay", "y'all", "yall",
)


def laugh_score(text: str, likes: int = 0) -> float:
    """Heuristic 'how funny / chaotic is this comment' score."""
    if not text:
        return 0.0
    t = text.lower()
    s = min(sum(text.count(e) for e in _LAUGH_EMOJI), 5) * 1.5
    s += 2 * sum(1 for w in _LAUGH_WORDS if w in t)
    if re.search(r"(.)\1\1", t):            # stretched letters: "lmaooo", "noooo"
        s += 1.5
    if re.search(r"\b[A-Z]{4,}\b", text):   # SHOUTING
        s += 1.0
    s += min((likes or 0) / 25.0, 4.0)      # popularity boost
    if len(re.findall(r"[a-zA-Z']{3,}", text)) < 3:   # mostly emoji/timestamps → not a "take"
        s *= 0.3
    return s


# ── Playful copy generators ────────────────────────────────────────────

def vibe_check(avg, loved, crit, disc) -> str:
    if crit and loved and avg <= -0.15:
        return (f"🍿 The villa's in shambles and the group chat is FEASTING — "
                f"**{crit}** is getting cooked while **{loved}** can do no wrong.")
    if disc and crit and avg < 0.1:
        return (f"👀 Tea is brewing. Everyone's yapping about **{disc}**, "
                f"and the **{crit}** slander is relentless.")
    if loved and avg >= 0.1:
        return f"💛 Weirdly wholesome era — **{loved}** has the fans in a full chokehold."
    return "🌴 Grab a drink — the villa's just getting started."


def drama_meter(view) -> tuple[float, str, str]:
    if view.empty:
        return 0.0, "😴 Crickets", "no chatter yet"
    neg = float((view["sentiment_score"] <= -0.15).mean())
    if neg >= 0.50:
        return neg, "💣 FULL VILLA MELTDOWN", "someone get the producers"
    if neg >= 0.38:
        return neg, "🔥 Drama escalating", "recoupling's about to be messy"
    if neg >= 0.25:
        return neg, "👀 Tea is brewing", "side-eyes all around"
    if neg >= 0.12:
        return neg, "🙂 Mostly chill", "a little spice, nothing wild"
    return neg, "☀️ Lovefest", "everyone's coupled up and happy"


def _label(score: float) -> str:
    if score >= 0.15:
        return "positive 🙂"
    if score <= -0.15:
        return "negative 🙁"
    return "neutral 😐"


def _roster(config) -> tuple[list, list]:
    ent = config.get("entities", {}) or {}
    contestants = [p["canonical"] for p in (ent.get("contestants") or []) if p.get("canonical")]
    couples = [c["canonical"] for c in (ent.get("couples") or []) if c.get("canonical")]
    return contestants, couples


def _comment_card(row) -> None:
    text = row["text"][:260] + ("…" if len(row["text"]) > 260 else "")
    st.markdown(f"> {text}")
    meta = []
    if row.get("entity"):
        meta.append(f"🏷️ {row['entity']}")
    if "label" in row and pd.notna(row.get("label")):
        meta.append(f"{row['label']} ({row['score']:+.2f})")
    meta.append(str(row.get("source", "")))
    if row.get("like_count"):
        meta.append(f"👍 {int(row['like_count'])}")
    if row.get("topic"):
        meta.append(str(row["topic"]))
    url = row.get("url") or ""
    line = " · ".join(m for m in meta if m)
    st.caption(line + (f" · [open]({url})" if str(url).startswith("http") else ""))


def _ranked_comments(df, by, ascending) -> None:
    if df.empty:
        st.caption("None yet.")
        return
    for _, row in df.sort_values(by, ascending=ascending).head(3).iterrows():
        _comment_card(row)


# ── UI ─────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    st.set_page_config(page_title="Love Island USA — Sentiment", layout="wide")
    st.title(f"🌴 {config.show} — Sentiment Tracker  (Season {config.season})")

    items = load_items()
    if items.empty:
        st.info("No data yet. In your terminal run:  `python -m loveisland run`")
        return
    scored = items.dropna(subset=["sentiment_score"])

    contestants, couples = _roster(config)
    valid_all = set(contestants) | set(couples)

    aspects = load_aspects()
    if not aspects.empty:  # only show entities on the configured roster
        aspects = aspects[aspects["entity"].isin(valid_all)]

    # Sidebar filters
    st.sidebar.header("Filters")
    sources = sorted(items["source"].dropna().unique().tolist())
    picked_sources = st.sidebar.multiselect("Sources", sources, default=sources)
    grain = st.sidebar.radio("Time grain", ["Hour", "6 hours", "Day"], index=1)
    rule = {"Hour": "1h", "6 hours": "6h", "Day": "1D"}[grain]
    view = scored[scored["source"].isin(picked_sources)] if not scored.empty else scored

    # Compute the headline entities (roster-only)
    loved = crit = disc = divisive = None
    if not aspects.empty:
        be = (aspects.groupby(["entity", "entity_type"])
              .agg(mentions=("sentiment_score", "size"), avg=("sentiment_score", "mean"))
              .reset_index())
        ranked = be[be["mentions"] >= 2]
        if not ranked.empty:
            loved = ranked.sort_values("avg", ascending=False).iloc[0]["entity"]
            crit = ranked.sort_values("avg").iloc[0]["entity"]
            disc = ranked.sort_values("mentions", ascending=False).iloc[0]["entity"]
        counts = aspects.groupby("entity").size()
        elig = counts[counts >= 3].index
        if len(elig):
            spread = (aspects[aspects["entity"].isin(elig)]
                      .groupby("entity")["sentiment_score"].std().dropna().sort_values(ascending=False))
            divisive = spread.index[0] if len(spread) else None

    avg = view["sentiment_score"].mean() if not view.empty else 0.0

    # ---- Vibe check ----
    st.markdown(f"### {vibe_check(avg, loved, crit, disc)}")

    # ---- Top-line cards ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💛 Fan favorite", loved or "—", "most loved" if loved else None)
    c2.metric("🔥 Getting cooked", crit or "—", "most dragged" if crit else None)
    c3.metric("🗣️ Main character", disc or "—", "most discussed" if disc else None)
    c4.metric("🎭 Most divisive", divisive or "—", "fans at war" if divisive else None)

    s1, s2, s3 = st.columns(3)
    s1.metric("Comments tracked", len(items))
    s2.metric("Overall mood", f"{avg:+.2f}", _label(avg))
    if not view.empty:
        s3.metric("The villa is", f"{(view['sentiment_score'] >= 0.15).mean()*100:.0f}% in love",
                  f"{(view['sentiment_score'] <= -0.15).mean()*100:.0f}% in their feelings")

    # ---- Drama-o-meter ----
    st.subheader("🌡️ Drama-o-meter")
    lvl, label, sub = drama_meter(view)
    st.progress(min(1.0, lvl + 0.05))
    st.markdown(f"**{label}** — _{sub}_")

    # ---- Funniest comments ----
    st.subheader("😂 Funniest comments right now")
    funny = items[items["laugh"] > 2].sort_values(["laugh", "like_count"], ascending=False).head(8)
    if funny.empty:
        st.caption("Nothing chaotic enough yet — give it a few runs. 🍿")
    else:
        for _, row in funny.iterrows():
            _comment_card(row)

    # ---- Sentiment over time ----
    st.subheader("Sentiment over time")
    if view.empty:
        st.caption("No scored comments in the selected sources yet.")
    else:
        ts = (view.set_index("created_et").resample(rule)["sentiment_score"]
              .mean().reset_index().dropna())
        if not ts.empty:
            line = (alt.Chart(ts).mark_line(point=True).encode(
                x=alt.X("created_et:T", title="Time (ET)"),
                y=alt.Y("sentiment_score:Q", title="Avg sentiment", scale=alt.Scale(domain=[-1, 1])),
                tooltip=["created_et:T", alt.Tooltip("sentiment_score:Q", format="+.2f")],
            ).properties(height=260))
            zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="gray").encode(y="y")
            st.altair_chart(zero + line, use_container_width=True)

    # ---- By contestant / couple ----
    st.subheader("By contestant / couple")
    if aspects.empty:
        st.caption("No per-person sentiment yet — score some comments first.")
    else:
        kind = st.radio("Show", ["Contestants", "Couples"], horizontal=True, key="overview_kind")
        want = "contestant" if kind == "Contestants" else "couple"
        sub_a = aspects[aspects["entity_type"] == want]
        if sub_a.empty:
            st.caption(f"No {kind.lower()} mentions yet.")
        else:
            agg = (sub_a.groupby("entity")
                   .agg(mentions=("sentiment_score", "size"), avg=("sentiment_score", "mean"))
                   .reset_index().sort_values("mentions", ascending=False))
            bar = (alt.Chart(agg).mark_bar().encode(
                x=alt.X("avg:Q", title="Avg sentiment", scale=alt.Scale(domain=[-1, 1])),
                y=alt.Y("entity:N", sort="-x", title=None),
                color=alt.Color("avg:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[-1, 1]),
                                legend=None),
                tooltip=["entity", "mentions", alt.Tooltip("avg:Q", format="+.2f")],
            ).properties(height=max(220, 26 * len(agg))))
            st.altair_chart(bar, use_container_width=True)

    # ---- Spotlight ----
    st.subheader("🔍 Spotlight — zoom in on one person or couple")
    s_kind = st.radio("Look at", ["Contestants", "Couples"], horizontal=True, key="spot_kind")
    roster = sorted(contestants) if s_kind == "Contestants" else sorted(couples)
    pick = st.selectbox("Choose", roster) if roster else None

    if pick:
        ent_comments = load_entity_comments(pick)
        asp = aspects[aspects["entity"] == pick]
        if asp.empty:
            st.info(f"No comments mention **{pick}** yet. Check back after more runs.")
        else:
            sc = asp["sentiment_score"].mean()
            a, b, c = st.columns(3)
            a.metric("Mentions", len(asp))
            b.metric("Avg sentiment", f"{sc:+.2f}", _label(sc))
            mode = asp["topic"].mode()
            c.metric("Top topic", mode.iloc[0] if not mode.empty else "—")

            topics = (asp.dropna(subset=["topic"]).groupby("topic")
                      .agg(mentions=("sentiment_score", "size"), avg=("sentiment_score", "mean"))
                      .reset_index())
            if not topics.empty:
                st.markdown("**What people talk about**")
                tbar = (alt.Chart(topics).mark_bar().encode(
                    x=alt.X("mentions:Q", title="Mentions"),
                    y=alt.Y("topic:N", sort="-x", title=None),
                    color=alt.Color("avg:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[-1, 1]),
                                    title="avg sentiment"),
                    tooltip=["topic", "mentions", alt.Tooltip("avg:Q", format="+.2f")],
                ).properties(height=max(120, 30 * len(topics))))
                st.altair_chart(tbar, use_container_width=True)

            left, right = st.columns(2)
            with left:
                st.markdown(f"**💛 Most loved about {pick}**")
                _ranked_comments(ent_comments, "score", ascending=False)
            with right:
                st.markdown(f"**🔥 Most dragged about {pick}**")
                _ranked_comments(ent_comments, "score", ascending=True)

            funny_e = ent_comments[ent_comments["laugh"] > 1.5]
            if not funny_e.empty:
                st.markdown(f"**😂 Funniest takes on {pick}**")
                _ranked_comments(funny_e, "laugh", ascending=False)

    # ---- By source & volume ----
    left, right = st.columns(2)
    with left:
        st.subheader("By source")
        if not scored.empty:
            src = (scored.groupby("source")
                   .agg(comments=("id", "size"), avg=("sentiment_score", "mean")).reset_index())
            st.dataframe(src.style.format({"avg": "{:+.2f}"}), use_container_width=True)
    with right:
        st.subheader("Volume over time")
        vol = (items.dropna(subset=["created_et"]).set_index("created_et")
               .resample(rule)["id"].count().rename("comments"))
        if not vol.empty:
            st.bar_chart(vol)


if __name__ == "__main__":
    main()
