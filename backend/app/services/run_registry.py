"""Tracks in-progress experiment runs (PRD section 31 live dashboard needs to poll status
before the final DB row exists). Purely in-memory -- one backend process per local run.
"""
from __future__ import annotations

import threading


class RunRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}

    def start(self, experiment_id: str, name: str) -> None:
        with self._lock:
            self._runs[experiment_id] = {"experiment_id": experiment_id, "name": name, "status": "running", "error": None}

    def complete(self, experiment_id: str) -> None:
        with self._lock:
            if experiment_id in self._runs:
                self._runs[experiment_id]["status"] = "completed"

    def fail(self, experiment_id: str, error: str) -> None:
        with self._lock:
            if experiment_id in self._runs:
                self._runs[experiment_id]["status"] = "failed"
                self._runs[experiment_id]["error"] = error

    def get(self, experiment_id: str) -> dict | None:
        with self._lock:
            return self._runs.get(experiment_id)


run_registry = RunRegistry()
