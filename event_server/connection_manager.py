"""Tracks connected workers: registration, heartbeats, and failure-detection status
(PRD sections 13, 23). Thread-safe: the server's accept-thread, per-connection reader
threads, and the heartbeat-timeout checker all touch this concurrently.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum

HEARTBEAT_INTERVAL_SECONDS = 5
SUSPECTED_TIMEOUT_SECONDS = 10
OFFLINE_TIMEOUT_SECONDS = 15


class WorkerStatus(str, Enum):
    ONLINE = "ONLINE"
    SUSPECTED = "SUSPECTED"
    OFFLINE = "OFFLINE"


@dataclass
class WorkerInfo:
    worker_id: str
    hostname: str
    language: str
    version: str
    connected_at: float
    status: WorkerStatus = WorkerStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.time)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    events_processed: int = 0
    events_failed: int = 0
    last_processed_sequence: int | None = None

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "language": self.language,
            "version": self.version,
            "status": self.status.value,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "last_heartbeat": self.last_heartbeat,
            "last_processed_sequence": self.last_processed_sequence,
        }


class ConnectionManager:
    def __init__(
        self,
        suspected_timeout: float = SUSPECTED_TIMEOUT_SECONDS,
        offline_timeout: float = OFFLINE_TIMEOUT_SECONDS,
    ):
        self._workers: dict[str, WorkerInfo] = {}
        self._connections: dict[str, object] = {}  # worker_id -> socket-like sender
        self._lock = threading.Lock()
        self._suspected_timeout = suspected_timeout
        self._offline_timeout = offline_timeout

    def register(self, worker_id: str, hostname: str, language: str, version: str, connection) -> WorkerInfo:
        with self._lock:
            info = WorkerInfo(
                worker_id=worker_id,
                hostname=hostname,
                language=language,
                version=version,
                connected_at=time.time(),
            )
            self._workers[worker_id] = info
            self._connections[worker_id] = connection
            return info

    def unregister(self, worker_id: str) -> None:
        with self._lock:
            self._connections.pop(worker_id, None)

    def update_heartbeat(self, worker_id: str, cpu_usage: float, memory_usage: float,
                          events_processed: int, events_failed: int,
                          last_processed_sequence: int | None) -> None:
        """Heartbeats only update liveness/telemetry -- never "current_job" assignment,
        to avoid a stale heartbeat racing against completion and re-marking a worker busy."""
        with self._lock:
            info = self._workers.get(worker_id)
            if info is None:
                return
            info.last_heartbeat = time.time()
            info.cpu_usage = cpu_usage
            info.memory_usage = memory_usage
            info.events_processed = events_processed
            info.events_failed = events_failed
            info.last_processed_sequence = last_processed_sequence
            if info.status != WorkerStatus.ONLINE:
                info.status = WorkerStatus.ONLINE

    def set_current_job(self, worker_id: str, job_id: str | None) -> None:
        with self._lock:
            info = self._workers.get(worker_id)
            if info is not None:
                info.current_job = job_id

    def get_connection(self, worker_id: str):
        with self._lock:
            return self._connections.get(worker_id)

    def get(self, worker_id: str) -> WorkerInfo | None:
        with self._lock:
            return self._workers.get(worker_id)

    def list_workers(self) -> list[WorkerInfo]:
        with self._lock:
            return list(self._workers.values())

    def online_worker_ids(self) -> list[str]:
        with self._lock:
            return [wid for wid, info in self._workers.items() if info.status == WorkerStatus.ONLINE]

    def check_timeouts(self) -> list[tuple[str, WorkerStatus]]:
        """Advance ONLINE -> SUSPECTED -> OFFLINE based on heartbeat age. Returns transitions."""
        now = time.time()
        transitions: list[tuple[str, WorkerStatus]] = []
        with self._lock:
            for info in self._workers.values():
                age = now - info.last_heartbeat
                new_status = info.status
                if age > self._offline_timeout:
                    new_status = WorkerStatus.OFFLINE
                elif age > self._suspected_timeout:
                    new_status = WorkerStatus.SUSPECTED
                if new_status != info.status:
                    info.status = new_status
                    transitions.append((info.worker_id, new_status))
        return transitions
