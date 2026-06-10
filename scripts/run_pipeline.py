#!/usr/bin/env python3
"""Scheduler entry point: collect + score in one go, with a timestamped log line.

Called automatically by the macOS scheduler (a LaunchAgent) every few hours.
Each run appends a timestamped section to outputs/cron.log so you can see its
history. Errors are logged, not raised, so one bad run never breaks the schedule.

You can also run it by hand any time:
    .venv/bin/python scripts/run_pipeline.py
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

# Make the package importable when run directly (not as `python -m`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"\n===== run @ {stamp} =====", flush=True)
    try:
        from loveisland.cli import main as cli_main
        cli_main(["run"])  # collect + score
    except Exception:  # never let the scheduler see a crash
        print("ERROR during run:", flush=True)
        traceback.print_exc()
    print("===== done =====", flush=True)


if __name__ == "__main__":
    main()
