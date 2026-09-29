"""Persists an ExperimentController result into Postgres/SQLite (PRD section 27)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.experiment import Experiment
from backend.app.models.failure import Failure
from backend.app.models.metric import Metric
from backend.app.models.worker import Worker
from experiment_controller.controller import ExperimentResult


def persist_experiment_result(db: Session, result: ExperimentResult) -> Experiment:
    experiment = Experiment(
        id=result.experiment_id,
        name=result.name,
        dataset=result.config["dataset_file"],
        protocol=result.config["protocol"],
        worker_language=result.config["worker_language"],
        worker_count=result.config["worker_count"],
        strategy=result.config["strategy"],
        status="completed",
    )
    db.add(experiment)
    db.flush()

    for w in result.workers:
        db.add(Worker(
            experiment_id=experiment.id,
            worker_id=w["worker_id"],
            language=w["language"],
            hostname=w["hostname"],
            status=w["status"],
            cpu_usage=w["cpu_usage"],
            memory_usage=w["memory_usage"],
            last_heartbeat=datetime.fromtimestamp(w["last_heartbeat"]) if w.get("last_heartbeat") else None,
        ))

    summary = result.aggregator_summary
    e2e = summary["end_to_end_latency_ms"]
    for worker_id, stats in summary["workers"].items():
        db.add(Metric(
            experiment_id=experiment.id,
            worker_id=worker_id,
            event_count=stats["events_processed"] + stats["events_failed"],
            throughput=result.replay_stats["events_per_sec"],
            avg_latency=e2e["avg"],
            p95_latency=e2e["p95"],
            p99_latency=e2e["p99"],
            cpu_usage=0.0,
            memory_usage=0.0,
        ))

    for f in result.failures:
        db.add(Failure(
            experiment_id=experiment.id,
            worker_id=f["worker_id"],
            detected_at=datetime.fromtimestamp(f["detected_at"]),
            recovered_at=datetime.fromtimestamp(f["recovered_at"]) if f.get("recovered_at") else None,
            recovery_time=f.get("recovery_time_seconds"),
        ))

    db.commit()
    db.refresh(experiment)
    return experiment


def mark_experiment_failed(db: Session, experiment_id: str, name: str, config: dict, error: str) -> Experiment:
    experiment = Experiment(
        id=experiment_id,
        name=name,
        description=error[:1000],
        dataset=config.get("dataset_file", ""),
        protocol=config.get("protocol", ""),
        worker_language=config.get("worker_language", ""),
        worker_count=config.get("worker_count", 0),
        strategy=config.get("strategy", ""),
        status="failed",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment
