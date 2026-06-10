"""Streamlit dashboard — answer-first sentiment view.

Layout (top to bottom):
  1. Top-line: overall sentiment, volume, most loved / criticized / discussed
  2. Sentiment over time (pick the time grain)
  3. By contestant / couple
  4. Spotlight — pick one person/couple: topics + most loved/dragged comments
  5. By source & volume over time

Only entities on the configured Season roster are shown anywhere.

Run with:  python -m loveisland serve
"""

from __future__ import annotations

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
    """Every comment that mentions one entity, with its per-entity sentiment."""
    with db.connect() as conn:
        return pd.read_sql_query(
            "SELECT i.text, i.source, i.url, i.like_count, a.topic, "
            "a.sentiment_score AS score, a.sentiment_label AS label "
            "FROM aspects a JOIN items i ON i.id = a.item_id WHERE a.entity = ?",
            conn, params=(entity,),
        )


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


def _show_comments(df: "pd.DataFrame", ascending: bool) -> None:
    """Render up to 3 comments ranked by sentiment, then likes."""
    if df.empty:
        st.caption("None yet.")
        return
    ranked = df.sort_values(["score", "like_count"], ascending=[ascending, False]).head(3)
    for _, c in ranked.iterrows():
        text = c["text"][:240] + ("…" if len(c["text"]) > 240 else "")
        st.markdown(f"> {text}")
        meta = f"{c['label']} ({c['score']:+.2f}) · {c['source']}"
        if c["like_count"]:
            meta += f" · 👍 {int(c['like_count'])}"
        if c["topic"]:
            meta += f" · {c['topic']}"
        url = c["url"] or ""
        st.caption(meta + (f" · [open]({url})" if url.startswith("http") else ""))


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
    if not aspects.empty:  # only ever show entities on the configured roster
        aspects = aspects[aspects["entity"].isin(valid_all)]

    # Sidebar filters
    st.sidebar.header("Filters")
    sources = sorted(items["source"].dropna().unique().tolist())
    picked_sources = st.sidebar.multiselect("Sources", sources, default=sources)
    grain = st.sidebar.radio("Time grain", ["Hour", "6 hours", "Day"], index=1)
    rule = {"Hour": "1h", "6 hours": "6h", "Day": "1D"}[grain]
    view = scored[scored["source"].isin(picked_sources)] if not scored.empty else scored

    # ---- 1. TOP-LINE -------------------------------------------------
    st.subheader("Top-line")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Comments collected", len(items))
    c1.metric("Scored", len(scored))
    avg = view["sentiment_score"].mean() if not view.empty else 0.0
    c2.metric("Overall sentiment", f"{avg:+.2f}", _label(avg))
    if not view.empty:
        c3.metric("Positive", f"{(view['sentiment_score'] >= 0.15).mean() * 100:.0f}%")
        c4.metric("Negative", f"{(view['sentiment_score'] <= -0.15).mean() * 100:.0f}%")

    if not aspects.empty:
        by_entity = (
            aspects.groupby(["entity", "entity_type"])
            .agg(mentions=("sentiment_score", "size"), avg=("sentiment_score", "mean"))
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

    # ---- 3. BY CONTESTANT / COUPLE (overview bar) -------------------
    st.subheader("By contestant / couple")
    if aspects.empty:
        st.caption("No per-person sentiment yet — score some comments first.")
    else:
        kind = st.radio("Show", ["Contestants", "Couples"], horizontal=True, key="overview_kind")
        want = "contestant" if kind == "Contestants" else "couple"
        sub = aspects[aspects["entity_type"] == want]
        if sub.empty:
            st.caption(f"No {kind.lower()} mentions yet.")
        else:
            agg = (sub.groupby("entity")
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

    # ---- 4. SPOTLIGHT -----------------------------------------------
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
            top_topic = asp["topic"].mode()
            c.metric("Top topic", top_topic.iloc[0] if not top_topic.empty else "—")

            # Topics they're discussed with
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
                st.markdown(f"**💛 Most loved comments about {pick}**")
                _show_comments(ent_comments, ascending=False)
            with right:
                st.markdown(f"**🔥 Most dragged comments about {pick}**")
                _show_comments(ent_comments, ascending=True)

    # ---- 5. BY SOURCE & VOLUME --------------------------------------
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
