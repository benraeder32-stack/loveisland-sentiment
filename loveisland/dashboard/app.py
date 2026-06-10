"""Streamlit dashboard — answer-first, and built to make people laugh.

Layout (top to bottom):
  • Vibe-check one-liner
  • 🏆 Burn of the Day (one savage comment, featured)
  • Top-line cards: fan favorite / getting cooked / main character / most divisive
  • 🌡️ Drama-o-meter
  • Sentiment over time
  • 😈 Villain Rankings  +  💕 Couple Chemistry Leaderboard
  • 🔍 Spotlight (per person/couple: topics, loved/dragged, funniest takes)
  • By source & volume

Humor is rated by the LLM (the `funny` field), not emoji counting. Only entities
on the configured Season roster are shown anywhere.

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


# ── Data loading ────────────────────────────────────────────────────────

def load_items() -> "pd.DataFrame":
    with db.connect() as conn:
        df = pd.read_sql_query(
            "SELECT id, source, episode, entity, entity_type, text, url, like_count, "
            "funny, created_at, sentiment_label, sentiment_score FROM items",
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
    with db.connect() as conn:
        return pd.read_sql_query(
            "SELECT i.text, i.source, i.url, i.like_count, i.funny, a.topic, "
            "a.sentiment_score AS score, a.sentiment_label AS label "
            "FROM aspects a JOIN items i ON i.id = a.item_id WHERE a.entity = ?",
            conn, params=(entity,),
        )


# ── Playful copy ────────────────────────────────────────────────────────

def vibe_check(avg, loved, crit, disc) -> str:
    if crit and loved and avg <= -0.15:
        return (f"🔪 It's a bloodbath in the group chat — **{crit}** is getting "
                f"dragged to filth while **{loved}** walks on water.")
    if disc and crit and avg < 0.05:
        return (f"☕ The tea is scalding. **{disc}** is all anyone can talk about, "
                f"and the **{crit}** slander is a full-time job.")
    if loved and avg >= 0.05:
        return f"😌 Rare peace in the villa — **{loved}** has the fans absolutely feral (affectionate)."
    return "🌴 Pour a drink — the villa's just warming up."


def drama_meter(view) -> tuple[float, str, str]:
    if view.empty:
        return 0.0, "😴 Crickets", "no chatter yet"
    neg = float((view["sentiment_score"] <= -0.15).mean())
    if neg >= 0.50:
        return neg, "💣 FULL VILLA MELTDOWN", "somebody call the producers"
    if neg >= 0.38:
        return neg, "🔥 Drama escalating", "the recoupling's gonna be a bloodbath"
    if neg >= 0.25:
        return neg, "☕ Tea is brewing", "side-eyes for days"
    if neg >= 0.12:
        return neg, "🙂 Mostly chill", "a little messy, nothing wild"
    return neg, "☀️ Lovefest", "everyone's coupled up and glowing"


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


def _ranking_bar(df, order: str):
    return (alt.Chart(df).mark_bar().encode(
        x=alt.X("avg:Q", title="avg sentiment", scale=alt.Scale(domain=[-1, 1])),
        y=alt.Y("entity:N", title=None, sort=alt.SortField("avg", order=order)),
        color=alt.Color("avg:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[-1, 1]),
                        legend=None),
        tooltip=["entity", "mentions", alt.Tooltip("avg:Q", format="+.2f")],
    ).properties(height=max(180, 28 * len(df))))


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
    if not aspects.empty:
        aspects = aspects[aspects["entity"].isin(valid_all)]

    # Sidebar filters
    st.sidebar.header("Filters")
    sources = sorted(items["source"].dropna().unique().tolist())
    picked_sources = st.sidebar.multiselect("Sources", sources, default=sources)
    grain = st.sidebar.radio("Time grain", ["Hour", "6 hours", "Day"], index=1)
    rule = {"Hour": "1h", "6 hours": "6h", "Day": "1D"}[grain]
    view = scored[scored["source"].isin(picked_sources)] if not scored.empty else scored

    # Headline entities (roster-only)
    loved = crit = disc = divisive = None
    by_entity = pd.DataFrame()
    if not aspects.empty:
        by_entity = (aspects.groupby(["entity", "entity_type"])
                     .agg(mentions=("sentiment_score", "size"), avg=("sentiment_score", "mean"))
                     .reset_index())
        ranked = by_entity[by_entity["mentions"] >= 2]
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

    # ---- 🏆 Burn of the Day  +  🔥 The Burn Book ----
    burns = items[(items["funny"] >= 0.4) & (items["sentiment_score"] < 0.0)]
    if burns.empty:
        burns = items[items["funny"] >= 0.45]
    burns = burns.sort_values(["funny", "like_count"], ascending=False)
    if not burns.empty:
        b = burns.iloc[0]
        st.subheader("🏆 Burn of the Day")
        with st.container(border=True):
            st.markdown(f"### “{b['text'][:300]}”")
            tag = f"🏷️ {b['entity']} · " if b.get("entity") else ""
            likes = f" · 👍 {int(b['like_count'])}" if b.get("like_count") else ""
            link = f" · [open]({b['url']})" if str(b.get("url", "")).startswith("http") else ""
            st.caption(f"{tag}{b['source']}{likes}{link}")

        more = burns.iloc[1:9]
        if not more.empty:
            with st.expander(f"🔥 The Burn Book — {len(more)} more savage takes", expanded=True):
                for _, row in more.iterrows():
                    _comment_card(row)

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

    # ---- Villain rankings + couple chemistry ----
    if not by_entity.empty:
        col_v, col_c = st.columns(2)
        with col_v:
            st.subheader("😈 Villain Rankings")
            st.caption("contestants the fans love to hate (most negative)")
            vil = (by_entity[(by_entity["entity_type"] == "contestant") & (by_entity["mentions"] >= 2)]
                   .sort_values("avg").head(8))
            if vil.empty:
                st.caption("Not enough mentions yet.")
            else:
                st.altair_chart(_ranking_bar(vil, "ascending"), use_container_width=True)
        with col_c:
            st.subheader("💕 Couple Chemistry")
            st.caption("ships ranked by the fans (best vibes on top)")
            chem = (by_entity[by_entity["entity_type"] == "couple"]
                    .sort_values("avg", ascending=False).head(8))
            if chem.empty:
                st.caption("No couple mentions yet.")
            else:
                st.altair_chart(_ranking_bar(chem, "descending"), use_container_width=True)

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

            funny_e = ent_comments[ent_comments["funny"] >= 0.4]
            if not funny_e.empty:
                st.markdown(f"**😂 Funniest takes on {pick}**")
                _ranked_comments(funny_e, "funny", ascending=False)

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
