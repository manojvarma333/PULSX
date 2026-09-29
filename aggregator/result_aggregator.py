"""Result Aggregator (PRD sections 25-26): merges per-worker results, tracks which
dispatched sequence numbers never came back (for gap detection / reassignment), and
computes network / processing / end-to-end latency distributions.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from metrics_engine.latency import compute_latency_stats
from replay.models import MarketEvent


@dataclass
class WorkerResultStats:
    events_processed: int = 0
    events_failed: int = 0


class ResultAggregator:
    def __init__(self):
        self._lock = threading.Lock()
        self._dispatched: dict[int, tuple[str, MarketEvent, float]] = {}  # seq -> (worker_id, event, dispatched_at)
        self._received: set[int] = set()
        self._per_worker: dict[str, WorkerResultStats] = {}
        self._network_latencies_ns: list[float] = []
        self._processing_latencies_ns: list[float] = []
        self._end_to_end_latencies_ns: list[float] = []

    def record_dispatch(self, worker_id: str, event: MarketEvent) -> None:
        with self._lock:
            self._dispatched[event.sequence_number] = (worker_id, event, time.time())

    def record_result(self, worker_id: str, payload: dict) -> None:
        sequence_number = payload["sequence_number"]
        t1 = payload.get("dispatched_at_ns")
        t2 = payload.get("received_at_ns")
        t4 = payload.get("processing_started_ns")
        t5 = payload.get("processing_completed_ns")
        t6 = time.perf_counter_ns()

        with self._lock:
            self._received.add(sequence_number)
            stats = self._per_worker.setdefault(worker_id, WorkerResultStats())
            if payload.get("success"):
                stats.events_processed += 1
            else:
                stats.events_failed += 1

            if t1 is not None and t2 is not None:
                self._network_latencies_ns.append(t2 - t1)
            if t4 is not None and t5 is not None:
                self._processing_latencies_ns.append(t5 - t4)
            if t1 is not None:
                self._end_to_end_latencies_ns.append(t6 - t1)

    def pending_for_worker(self, worker_id: str) -> list[tuple[int, MarketEvent]]:
        """Events dispatched to `worker_id` that never received a result -- candidates
        for reassignment when that worker is declared OFFLINE."""
        with self._lock:
            return [
                (seq, event)
                for seq, (wid, event, _dispatched_at) in self._dispatched.items()
                if wid == worker_id and seq not in self._received
            ]

    def mark_reassigned(self, sequence_numbers: list[int]) -> None:
        with self._lock:
            for seq in sequence_numbers:
                self._dispatched.pop(seq, None)

    def missing_sequences(self) -> list[int]:
        """Dispatched sequence numbers with no result yet (PRD section 25)."""
        with self._lock:
            return sorted(set(self._dispatched) - self._received)

    def summary(self) -> dict:
        with self._lock:
            events_dispatched = len(self._dispatched)
            events_received = len(self._received)
            missing = sorted(set(self._dispatched) - self._received)
            per_worker = {
                worker_id: {"events_processed": s.events_processed, "events_failed": s.events_failed}
                for worker_id, s in self._per_worker.items()
            }
            network_ns = list(self._network_latencies_ns)
            processing_ns = list(self._processing_latencies_ns)
            end_to_end_ns = list(self._end_to_end_latencies_ns)

        to_ms = lambda values: [v / 1_000_000 for v in values]  # noqa: E731
        return {
            "events_dispatched": events_dispatched,
            "events_received": events_received,
            "missing_events": missing,
            "workers": per_worker,
            "network_latency_ms": compute_latency_stats(to_ms(network_ns)).as_dict(),
            "processing_latency_ms": compute_latency_stats(to_ms(processing_ns)).as_dict(),
            "end_to_end_latency_ms": compute_latency_stats(to_ms(end_to_end_ns)).as_dict(),
        }
