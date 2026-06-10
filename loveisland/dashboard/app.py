"""Streamlit dashboard.

STATUS: placeholder. The real, answer-first dashboard (top-line sentiment and
biggest movers first, then trends, by contestant/couple, by source, and volume)
is built in the dashboard step. For now this confirms the wiring works.

Run with:  python -m loveisland serve
"""

from __future__ import annotations

try:
    import streamlit as st
except ImportError:  # streamlit is installed in the dashboard step
    st = None


def main() -> None:
    if st is None:
        print("Streamlit is not installed yet (added in the dashboard step).")
        return
    st.set_page_config(page_title="Love Island USA — Sentiment", layout="wide")
    st.title("Love Island USA — Sentiment Tracker")
    st.info("Dashboard coming soon. The data pipeline is being built step by step.")


if st is not None:
    main()
