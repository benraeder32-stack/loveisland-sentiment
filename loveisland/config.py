"""Loads settings from ``config.yaml`` and secrets from ``.env``.

Everything else in the project asks this module for configuration, so there is
a single, predictable place where settings come from.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

# Project root = the folder that contains this package.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
ENV_PATH = ROOT / ".env"

# Load .env into the environment once, on import (no error if it is missing).
load_dotenv(ENV_PATH)


class Config:
    """Thin wrapper around the parsed config.yaml dictionary."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    # -- whole sections -------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def show(self) -> str:
        return self._data.get("show", "Love Island USA")

    @property
    def season(self) -> int:
        return int(self._data.get("season", 0))


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Read and parse config.yaml."""
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Copy and edit the provided config.yaml."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(data)


def get_secret(name: str, required: bool = False, default: Optional[str] = None) -> Optional[str]:
    """Read a secret/key from the environment (loaded from .env).

    Set ``required=True`` to raise a clear error when the key is missing.
    """
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. "
            f"Add it to your .env file (see .env.example)."
        )
    return value
