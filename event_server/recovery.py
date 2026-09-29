"""Failure Recovery Manager (PRD section 24): when a worker is declared OFFLINE, its
in-flight (dispatched-but-unresulted) events are reassigned to another online worker.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aggregator.result_aggregator import ResultAggregator
from event_server.connection_manager import WorkerStatus
from event_server.distributor import EventDistributor

logger = logging.getLogger("pulsex.recovery")


@dataclass
class FailureRecord:
    worker_id: str
    detected_at: float
    pending_events: int
    reassigned_events: int
    recovery_time_seconds: float
    recovered_at: float | None = None


class RecoveryManager:
    def __init__(self, aggregator: ResultAggregator, distributor: EventDistributor):
        self._aggregator = aggregator
        self._distributor = distributor
        self.failures: list[FailureRecord] = []

    def on_worker_status_change(self, worker_id: str, status: WorkerStatus) -> None:
        if status != WorkerStatus.OFFLINE:
            return

        detected_at = time.time()
        pending = self._aggregator.pending_for_worker(worker_id)
        reassigned = 0
        for _sequence_number, event in pending:
            if self._distributor.publish(event):
                reassigned += 1
        self._aggregator.mark_reassigned([seq for seq, _event in pending])
        recovered_at = time.time()

        record = FailureRecord(
            worker_id=worker_id,
            detected_at=detected_at,
            pending_events=len(pending),
            reassigned_events=reassigned,
            recovery_time_seconds=recovered_at - detected_at,
            recovered_at=recovered_at,
        )
        self.failures.append(record)
        logger.warning(
            "worker %s OFFLINE -> reassigned %d/%d pending events",
            worker_id, reassigned, len(pending),
        )
