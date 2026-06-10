#!/usr/bin/env python3
"""Cron-friendly entry point: collect + score in one go.

Designed to be called on a schedule (cron or APScheduler). It simply invokes
the same ``run`` command the CLI exposes, so behavior stays consistent.

STATUS: placeholder. Scheduling details and the APScheduler option are
documented in the scheduler step.

Example cron line (every 2 hours):
    0 */2 * * *  cd /path/to/repo && .venv/bin/python -m loveisland run >> outputs/cron.log 2>&1
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure the package is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    from loveisland.cli import main as cli_main

    cli_main(["run"])


if __name__ == "__main__":
    main()
