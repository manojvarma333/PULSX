"""Replay engine (PRD section 10): publishes MarketEvents in order at a configurable rate.

Decoupled from transport: callers supply a `publish` callable (e.g. a TCP client's send
method). This keeps networking separate from replay/timing logic.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum

from replay.models import MarketEvent

PublishFn = Callable[[MarketEvent], bool]


class ReplayMode(str, Enum):
    ORIGINAL = "original"
    ACCELERATED = "accelerated"
    MAXIMUM = "maximum"


@dataclass
class ReplayStats:
    events_sent: int = 0
    dropped_events: int = 0
    connection_errors: int = 0
    start_time_ns: int = 0
    end_time_ns: int = 0

    @property
    def duration_seconds(self) -> float:
        return max(self.end_time_ns - self.start_time_ns, 0) / 1_000_000_000

    @property
    def events_per_sec(self) -> float:
        duration = self.duration_seconds
        return self.events_sent / duration if duration > 0 else float(self.events_sent)

    def summary(self) -> dict:
        return {
            "events_sent": self.events_sent,
            "dropped_events": self.dropped_events,
            "connection_errors": self.connection_errors,
            "replay_duration_seconds": round(self.duration_seconds, 6),
            "events_per_sec": round(self.events_per_sec, 2),
        }


class ReplayEngine:
    """Replays MarketEvents in timestamp order at Original/Accelerated/Maximum speed."""

    def __init__(
        self,
        events: Iterable[MarketEvent],
        publish: PublishFn,
        mode: ReplayMode = ReplayMode.ORIGINAL,
        speed_multiplier: float = 1.0,
        timestamp_unit_seconds: float = 1e-6,  # generator emits microsecond timestamps
    ):
        if mode == ReplayMode.ACCELERATED and speed_multiplier <= 0:
            raise ValueError("speed_multiplier must be > 0 for accelerated mode")

        self._events = events
        self._publish = publish
        self._mode = mode
        self._speed_multiplier = speed_multiplier
        self._timestamp_unit_seconds = timestamp_unit_seconds

    def run(self) -> ReplayStats:
        stats = ReplayStats(start_time_ns=time.perf_counter_ns())
        previous_timestamp: int | None = None

        for event in self._events:
            if self._mode != ReplayMode.MAXIMUM and previous_timestamp is not None:
                delta_units = event.timestamp - previous_timestamp
                if delta_units > 0:
                    sleep_seconds = delta_units * self._timestamp_unit_seconds
                    if self._mode == ReplayMode.ACCELERATED:
                        sleep_seconds /= self._speed_multiplier
                    if sleep_seconds > 0:
                        time.sleep(sleep_seconds)
            previous_timestamp = event.timestamp

            try:
                sent = self._publish(event)
            except (OSError, ConnectionError):
                stats.connection_errors += 1
                continue

            if sent:
                stats.events_sent += 1
            else:
                stats.dropped_events += 1

        stats.end_time_ns = time.perf_counter_ns()
        return stats
