"""Experiment orchestration + query API (PRD sections 26-28)."""
from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database.session import get_db, get_session_local
from backend.app.models.experiment import Experiment
from backend.app.services.experiment_service import mark_experiment_failed, persist_experiment_result
from backend.app.services.run_registry import run_registry
from experiment_controller.config import ExperimentConfig
from experiment_controller.controller import ExperimentController

router = APIRouter(prefix="/experiments", tags=["experiments"])


class RunExperimentRequest(BaseModel):
    name: str
    dataset_file: str
    protocol: str = "json"
    worker_language: str = "python"
    worker_count: int = 1
    strategy: str = "passthrough"
    strategy_kwargs: dict = Field(default_factory=dict)
    replay_mode: str = "maximum"
    speed_multiplier: float = 1.0
    heartbeat_interval: float = 5.0
    completion_timeout: float = 30.0
    cpp_worker_binary: str = "workers/cpp/build/pulsex_cpp_worker"
    worker_launch_mode: str = "thread"


@router.post("/run", status_code=202)
def run_experiment(request: RunExperimentRequest) -> dict:
    """Starts an experiment in a background thread and returns immediately (PRD section
    31's live dashboard polls GET /experiments/{id}/status while it runs)."""
    config = ExperimentConfig(
        name=request.name,
        dataset_file=request.dataset_file,
        protocol=request.protocol,
        worker_language=request.worker_language,
        worker_count=request.worker_count,
        strategy=request.strategy,
        strategy_kwargs=request.strategy_kwargs,
        replay_mode=request.replay_mode,
        speed_multiplier=request.speed_multiplier,
        heartbeat_interval=request.heartbeat_interval,
        completion_timeout=request.completion_timeout,
        cpp_worker_binary=request.cpp_worker_binary,
    )
    controller = ExperimentController(config, worker_launch_mode=request.worker_launch_mode)
    experiment_id = str(uuid.uuid4())
    run_registry.start(experiment_id, request.name)

    def _run() -> None:
        db = get_session_local()()
        try:
            result = controller.run(experiment_id=experiment_id)
            persist_experiment_result(db, result)
            run_registry.complete(experiment_id)
        except Exception as exc:  # noqa: BLE001 - background thread must not crash silently
            mark_experiment_failed(db, experiment_id, request.name, config.as_dict(), str(exc))
            run_registry.fail(experiment_id, str(exc))
        finally:
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return {"experiment_id": experiment_id, "status": "running"}


@router.get("/{experiment_id}/status")
def get_status(experiment_id: str) -> dict:
    status = run_registry.get(experiment_id)
    if status is None:
        raise HTTPException(status_code=404, detail="unknown experiment_id")
    return status


@router.get("")
def list_experiments(db: Session = Depends(get_db)) -> list[dict]:
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    return [_experiment_to_dict(e) for e in experiments]


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return _experiment_to_dict(experiment, detailed=True)


def _experiment_to_dict(experiment: Experiment, detailed: bool = False) -> dict:
    d = {
        "id": experiment.id,
        "name": experiment.name,
        "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
        "dataset": experiment.dataset,
        "protocol": experiment.protocol,
        "worker_language": experiment.worker_language,
        "worker_count": experiment.worker_count,
        "strategy": experiment.strategy,
        "status": experiment.status,
    }
    if detailed:
        d["workers"] = [
            {
                "worker_id": w.worker_id, "language": w.language, "status": w.status,
                "cpu_usage": w.cpu_usage, "memory_usage": w.memory_usage,
            }
            for w in experiment.workers
        ]
        d["metrics"] = [
            {
                "worker_id": m.worker_id, "event_count": m.event_count, "throughput": m.throughput,
                "avg_latency": m.avg_latency, "p95_latency": m.p95_latency, "p99_latency": m.p99_latency,
            }
            for m in experiment.metrics
        ]
        d["failures"] = [
            {
                "worker_id": f.worker_id, "failure_type": f.failure_type,
                "detected_at": f.detected_at.isoformat() if f.detected_at else None,
                "recovery_time": f.recovery_time,
            }
            for f in experiment.failures
        ]
    return d
