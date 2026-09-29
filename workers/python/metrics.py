"""Per-worker metrics collection (PRD section 13). Thin wrapper around metrics_engine
so the worker code reads naturally; the actual computation lives in one shared place.
"""
from __future__ import annotations

from metrics_engine.system import sample_process_usage


class WorkerMetrics:
    def __init__(self):
        self.events_processed = 0
        self.events_failed = 0
        self.last_processed_sequence: int | None = None

    def record_success(self, sequence_number: int) -> None:
        self.events_processed += 1
        self.last_processed_sequence = sequence_number

    def record_failure(self, sequence_number: int) -> None:
        self.events_failed += 1
        self.last_processed_sequence = sequence_number

    def snapshot(self) -> dict:
        usage = sample_process_usage()
        return {
            "cpu_usage": usage["cpu_usage"],
            "memory_usage": usage["memory_usage"],
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "last_processed_sequence": self.last_processed_sequence,
        }
