"""Streamlit dashboard — answer-first sentiment view.

Layout (top to bottom):
  1. Top-line: overall sentiment, volume, most loved / criticized / discussed
  2. Sentiment over time (pick the time grain)
  3. By contestant / couple
  4. By source
  5. Volume over time

Run with:  python -m loveisland serve
"""

from __future__ import annotations

import sqlite3

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


# ── Data loading (pure functions, so they're testable without Streamlit) ──

def load_items() -> "pd.DataFrame":
    with db.connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, source, episode, entity, entity_type, text, url, "
            "created_at, sentiment_label, sentiment_score FROM items",
            conn,
        )
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        df["created_et"] = df["created_at"].dt.tz_convert(EASTERN)
    return df


def load_aspects() -> "pd.DataFrame":
    with db.connect() as conn:
        return pd.read_sql_query(
            "SELECT a.entity, a.entity_type, a.topic, a.sentiment_label, "
            "a.sentiment_score, i.created_at FROM aspects a "
            "JOIN items i ON i.id = a.item_id",
            conn,
        )


def _label(score: float) -> str:
    if score >= 0.15:
        return "positive 🙂"
    if score <= -0.15:
        return "negative 🙁"
    return "neutral 😐"


# ── UI ────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    st.set_page_config(page_title="Love Island USA — Sentiment", layout="wide")
    st.title(f"🌴 {config.show} — Sentiment Tracker  (Season {config.season})")

    items = load_items()
    scored = items.dropna(subset=["sentiment_score"]) if not items.empty else items

    if items.empty:
        st.info("No data yet. In your terminal run:  `python -m loveisland run`")
        return

    # Sidebar filters
    st.sidebar.header("Filters")
    sources = sorted(items["source"].dropna().unique().tolist())
    picked_sources = st.sidebar.multiselect("Sources", sources, default=sources)
    grain = st.sidebar.radio("Time grain", ["Hour", "6 hours", "Day"], index=1)

    view = scored[scored["source"].isin(picked_sources)] if not scored.empty else scored
    aspects = load_aspects()

    # ---- 1. TOP-LINE -------------------------------------------------
    st.subheader("Top-line")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Comments collected", len(items))
    c1.metric("Scored", len(scored))
    avg = view["sentiment_score"].mean() if not view.empty else 0.0
    c2.metric("Overall sentiment", f"{avg:+.2f}", _label(avg))
    if not view.empty:
        pos = (view["sentiment_score"] >= 0.15).mean() * 100
        neg = (view["sentiment_score"] <= -0.15).mean() * 100
        c3.metric("Positive", f"{pos:.0f}%")
        c4.metric("Negative", f"{neg:.0f}%")

    # Most loved / criticized / discussed (from per-entity aspects)
    if not aspects.empty:
        by_entity = (
            aspects.groupby(["entity", "entity_type"])
            .agg(mentions=("sentiment_score", "size"),
                 avg=("sentiment_score", "mean"))
            .reset_index()
        )
        ranked = by_entity[by_entity["mentions"] >= 2]
        if not ranked.empty:
            m1, m2, m3 = st.columns(3)
            loved = ranked.sort_values("avg", ascending=False).iloc[0]
            crit = ranked.sort_values("avg").iloc[0]
            disc = ranked.sort_values("mentions", ascending=False).iloc[0]
            m1.metric("💛 Most loved", loved["entity"], f"{loved['avg']:+.2f}")
            m2.metric("🔥 Most criticized", crit["entity"], f"{crit['avg']:+.2f}")
            m3.metric("🗣️ Most discussed", disc["entity"], f"{int(disc['mentions'])} mentions")

    # ---- 2. SENTIMENT OVER TIME -------------------------------------
    st.subheader("Sentiment over time")
    if view.empty:
        st.caption("No scored comments in the selected sources yet.")
    else:
        rule = {"Hour": "1h", "6 hours": "6h", "Day": "1D"}[grain]
        ts = (
            view.set_index("created_et")
            .resample(rule)["sentiment_score"]
            .mean()
            .reset_index()
            .dropna()
        )
        if not ts.empty:
            line = (
                alt.Chart(ts)
                .mark_line(point=True)
                .encode(
                    x=alt.X("created_et:T", title="Time (ET)"),
                    y=alt.Y("sentiment_score:Q", title="Avg sentiment",
                            scale=alt.Scale(domain=[-1, 1])),
                    tooltip=["created_et:T", alt.Tooltip("sentiment_score:Q", format="+.2f")],
                )
                .properties(height=260)
            )
            zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="gray").encode(y="y")
            st.altair_chart(zero + line, use_container_width=True)

    # ---- 3. BY CONTESTANT / COUPLE ----------------------------------
    st.subheader("By contestant / couple")
    if aspects.empty:
        st.caption("No per-person sentiment yet — score some comments first.")
    else:
        kind = st.radio("Show", ["Contestants", "Couples"], horizontal=True)
        want = "contestant" if kind == "Contestants" else "couple"
        sub = aspects[aspects["entity_type"] == want]
        if sub.empty:
            st.caption(f"No {kind.lower()} mentions yet.")
        else:
            agg = (
                sub.groupby("entity")
                .agg(mentions=("sentiment_score", "size"),
                     avg=("sentiment_score", "mean"))
                .reset_index()
                .sort_values("mentions", ascending=False)
            )
            bar = (
                alt.Chart(agg)
                .mark_bar()
                .encode(
                    x=alt.X("avg:Q", title="Avg sentiment", scale=alt.Scale(domain=[-1, 1])),
                    y=alt.Y("entity:N", sort="-x", title=None),
                    color=alt.Color("avg:Q", scale=alt.Scale(scheme="redyellowgreen",
                                                              domain=[-1, 1]), legend=None),
                    tooltip=["entity", "mentions", alt.Tooltip("avg:Q", format="+.2f")],
                )
                .properties(height=max(220, 26 * len(agg)))
            )
            st.altair_chart(bar, use_container_width=True)

    # ---- 4. BY SOURCE & 5. VOLUME -----------------------------------
    left, right = st.columns(2)
    with left:
        st.subheader("By source")
        if not scored.empty:
            src = (
                scored.groupby("source")
                .agg(comments=("id", "size"), avg=("sentiment_score", "mean"))
                .reset_index()
            )
            st.dataframe(src.style.format({"avg": "{:+.2f}"}), use_container_width=True)
    with right:
        st.subheader("Volume over time")
        rule = {"Hour": "1h", "6 hours": "6h", "Day": "1D"}[grain]
        vol = (
            items.dropna(subset=["created_et"])
            .set_index("created_et")
            .resample(rule)["id"].count()
            .rename("comments")
        )
        if not vol.empty:
            st.bar_chart(vol)


if __name__ == "__main__":
    main()
