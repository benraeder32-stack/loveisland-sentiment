"""Command-line interface.

Usage:
    python -m loveisland init-db
    python -m loveisland collect [--since YYYY-MM-DD] [--source youtube,news]
    python -m loveisland score   [--limit N] [--model MODEL]
    python -m loveisland run      [--since YYYY-MM-DD] [--source youtube,news]
    python -m loveisland serve
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Quiet harmless environment notices (old Python / LibreSSL) so output stays clean.
warnings.filterwarnings("ignore", category=FutureWarning, module=r"google\..*")
warnings.filterwarnings("ignore", message=r".*OpenSSL.*")

from . import __version__, pipeline
from .config import ROOT, load_config


def _parse_since(value: str | None) -> datetime:
    """Parse --since (an ISO date) or default to 2 days ago (UTC)."""
    if not value:
        return datetime.now(timezone.utc) - timedelta(days=2)
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise SystemExit(f"Could not read --since {value!r}. Use e.g. 2026-06-08.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _split_sources(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


def _not_ready(message: str) -> None:
    print(f"⏳ {message}")
    print("   (This piece is built in a later step — the skeleton is in place.)")


def cmd_init_db(args: argparse.Namespace) -> None:
    from .store import db
    try:
        db.init_db()
        print("✅ Database ready.")
    except NotImplementedError as exc:
        _not_ready(str(exc))


def cmd_collect(args: argparse.Namespace) -> None:
    config = load_config()
    try:
        added = pipeline.collect(
            config, _parse_since(args.since), _split_sources(args.source)
        )
        print(f"✅ Collected {added} new item(s).")
    except NotImplementedError as exc:
        _not_ready(str(exc))


def cmd_score(args: argparse.Namespace) -> None:
    config = load_config()
    try:
        scored = pipeline.score(config, args.limit, args.model)
        print(f"✅ Scored {scored} item(s).")
    except NotImplementedError as exc:
        _not_ready(str(exc))


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config()
    try:
        added, scored = pipeline.run(
            config, _parse_since(args.since), _split_sources(args.source)
        )
        print(f"✅ Collected {added} item(s), scored {scored}.")
    except NotImplementedError as exc:
        _not_ready(str(exc))


def cmd_serve(args: argparse.Namespace) -> None:
    app = ROOT / "loveisland" / "dashboard" / "app.py"
    print("🚀 Launching dashboard (press Ctrl+C to stop)…")
    try:
        subprocess.run(["streamlit", "run", str(app)], check=True)
    except FileNotFoundError:
        print("Streamlit is not installed yet. It is added in the dashboard step.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loveisland",
        description="Love Island USA sentiment tracker.",
    )
    parser.add_argument("--version", action="version", version=f"loveisland {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create the database and tables.").set_defaults(func=cmd_init_db)

    p_collect = sub.add_parser("collect", help="Gather comments from sources.")
    p_collect.add_argument("--since", help="ISO date, e.g. 2026-06-08 (default: 2 days ago)")
    p_collect.add_argument("--source", help="Comma-separated: youtube,news")
    p_collect.set_defaults(func=cmd_collect)

    p_score = sub.add_parser("score", help="Score sentiment of unscored items.")
    p_score.add_argument("--limit", type=int, help="Max items to score this run")
    p_score.add_argument("--model", help="Override the Claude model id")
    p_score.set_defaults(func=cmd_score)

    p_run = sub.add_parser("run", help="Collect then score (the usual command).")
    p_run.add_argument("--since", help="ISO date, e.g. 2026-06-08 (default: 2 days ago)")
    p_run.add_argument("--source", help="Comma-separated: youtube,news")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("serve", help="Open the dashboard in your browser.").set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
