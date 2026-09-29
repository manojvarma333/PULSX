"""Experiment Controller (PRD section 28): validates config, starts the TCP event server,
launches workers, replays the dataset, waits for completion, and returns a full result
(with reproducibility metadata per PRD section 29) ready to be persisted/reported.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from aggregator.result_aggregator import ResultAggregator
from event_server.distributor import EventDistributor
from event_server.recovery import RecoveryManager
from event_server.server import TCPEventServer
from experiment_controller.config import ExperimentConfig
from experiment_controller.system_info import collect_system_info
from replay.data_loader import DataLoader
from replay.replay_engine import ReplayEngine, ReplayMode
from workers.python.worker import PulseXWorker

logger = logging.getLogger("pulsex.experiment_controller")


@dataclass
class ExperimentResult:
    experiment_id: str
    name: str
    config: dict
    system_info: dict
    replay_stats: dict
    aggregator_summary: dict
    workers: list[dict]
    failures: list[dict]
    started_at: str
    finished_at: str

    @property
    def duration_seconds(self) -> float:
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.finished_at)
        return (end - start).total_seconds()


class _ThreadWorkerHandle:
    def __init__(self, worker: PulseXWorker, thread: threading.Thread):
        self.worker = worker
        self.thread = thread

    def stop(self, timeout: float = 3.0) -> None:
        self.worker.stop()
        self.thread.join(timeout=timeout)


class _ProcessWorkerHandle:
    def __init__(self, process: subprocess.Popen):
        self.process = process

    def stop(self, timeout: float = 3.0) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()


class ExperimentController:
    def __init__(
        self,
        config: ExperimentConfig,
        host: str = "127.0.0.1",
        port: int = 0,
        worker_launch_mode: str = "thread",  # "thread" | "process" | "external" (see below)
    ):
        if worker_launch_mode not in ("thread", "process", "external"):
            raise ValueError("worker_launch_mode must be 'thread', 'process', or 'external'")
        if config.worker_language == "cpp" and worker_launch_mode == "thread":
            raise ValueError("C++ workers must use worker_launch_mode='process' or 'external'")
        self.config = config
        self.host = host
        self.port = port
        self.worker_launch_mode = worker_launch_mode

    def run(self, experiment_id: str | None = None) -> ExperimentResult:
        experiment_id = experiment_id or str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("experiment %s (%s) starting", experiment_id, self.config.name)

        aggregator = ResultAggregator()
        server = TCPEventServer(host=self.host, port=self.port, on_result=aggregator.record_result)
        server.start()
        distributor = EventDistributor(server, binary_protocol=(self.config.protocol == "binary"), aggregator=aggregator)
        recovery = RecoveryManager(aggregator, distributor)
        server.on_worker_status_change = recovery.on_worker_status_change

        worker_handles = []
        try:
            worker_handles = self._spawn_workers(server.actual_port)
            self._wait_for_workers_online(server, expected=self.config.worker_count)

            loader = DataLoader(validate=True)
            events = loader.load(self.config.dataset_file)
            engine = ReplayEngine(
                events,
                publish=distributor.publish,
                mode=ReplayMode(self.config.replay_mode),
                speed_multiplier=self.config.speed_multiplier,
            )
            replay_stats = engine.run()

            self._wait_for_completion(aggregator, timeout=self.config.completion_timeout)

            summary = aggregator.summary()
            workers_info = [w.to_dict() for w in server.connection_manager.list_workers()]
            failures_info = [vars(f) for f in recovery.failures]
        finally:
            for handle in worker_handles:
                handle.stop()
            server.stop()

        finished_at = datetime.now(timezone.utc).isoformat()
        result = ExperimentResult(
            experiment_id=experiment_id,
            name=self.config.name,
            config=self.config.as_dict(),
            system_info=collect_system_info(),
            replay_stats=replay_stats.summary(),
            aggregator_summary=summary,
            workers=workers_info,
            failures=failures_info,
            started_at=started_at,
            finished_at=finished_at,
        )
        logger.info(
            "experiment %s finished: sent=%d received=%d missing=%d",
            experiment_id, replay_stats.events_sent, summary["events_received"], len(summary["missing_events"]),
        )
        return result

    def _spawn_workers(self, port: int) -> list:
        if self.worker_launch_mode == "external":
            return []  # workers are already-running processes/containers connecting in on their own
        if self.config.worker_language == "cpp":
            return self._spawn_cpp_workers(port)
        if self.worker_launch_mode == "process":
            return self._spawn_python_process_workers(port)
        return self._spawn_python_thread_workers(port)

    def _spawn_python_thread_workers(self, port: int) -> list[_ThreadWorkerHandle]:
        handles = []
        for i in range(self.config.worker_count):
            worker = PulseXWorker(
                worker_id=f"py-thread-{i}",
                host=self.host,
                port=port,
                strategy_name=self.config.strategy,
                strategy_kwargs=self.config.strategy_kwargs,
                heartbeat_interval=self.config.heartbeat_interval,
            )
            thread = threading.Thread(target=worker.run_forever, daemon=True)
            thread.start()
            handles.append(_ThreadWorkerHandle(worker, thread))
        return handles

    def _spawn_python_process_workers(self, port: int) -> list[_ProcessWorkerHandle]:
        handles = []
        for i in range(self.config.worker_count):
            cmd = [
                sys.executable, "-m", "workers.python.worker",
                "--worker-id", f"py-proc-{i}",
                "--host", self.host,
                "--port", str(port),
                "--strategy", self.config.strategy,
                "--heartbeat-interval", str(self.config.heartbeat_interval),
            ]
            proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent.parent))
            handles.append(_ProcessWorkerHandle(proc))
        return handles

    def _spawn_cpp_workers(self, port: int) -> list[_ProcessWorkerHandle]:
        binary = Path(self.config.cpp_worker_binary)
        if not binary.exists():
            raise RuntimeError(
                f"C++ worker binary not found at {binary}. Build it first, e.g. via "
                "`docker compose build cpp-worker` or CMake (see workers/cpp/README)."
            )
        handles = []
        for i in range(self.config.worker_count):
            cmd = [
                str(binary),
                "--worker-id", f"cpp-{i}",
                "--host", self.host,
                "--port", str(port),
                "--strategy", self.config.strategy,
            ]
            proc = subprocess.Popen(cmd)
            handles.append(_ProcessWorkerHandle(proc))
        return handles

    def _wait_for_workers_online(self, server: TCPEventServer, expected: int, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(server.connection_manager.online_worker_ids()) >= expected:
                return
            time.sleep(0.05)
        online = len(server.connection_manager.online_worker_ids())
        raise TimeoutError(f"only {online}/{expected} workers came online within {timeout}s")

    def _wait_for_completion(self, aggregator: ResultAggregator, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            summary = aggregator.summary()
            if summary["events_dispatched"] > 0 and summary["events_received"] >= summary["events_dispatched"]:
                return
            time.sleep(0.05)
        logger.warning("experiment completion timed out after %ss; some results may be missing", timeout)
