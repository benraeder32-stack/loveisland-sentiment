"""Collectors: one module per data source, all sharing the Collector interface."""

from .base import Collector

__all__ = ["Collector"]
