"""Throughput helpers (PRD section 19)."""
from __future__ import annotations


def events_per_second(event_count: int, duration_seconds: float) -> float:
    if duration_seconds <= 0:
        return float(event_count)
    return event_count / duration_seconds
