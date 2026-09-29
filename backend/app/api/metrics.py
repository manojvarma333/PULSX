"""Throughput / latency query API (PRD sections 33-34)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.metric import Metric

router = APIRouter(prefix="/experiments/{experiment_id}/metrics", tags=["metrics"])


@router.get("")
def list_metrics(experiment_id: str, db: Session = Depends(get_db)) -> list[dict]:
    metrics = db.query(Metric).filter(Metric.experiment_id == experiment_id).all()
    return [
        {
            "worker_id": m.worker_id, "event_count": m.event_count, "throughput": m.throughput,
            "avg_latency": m.avg_latency, "p95_latency": m.p95_latency, "p99_latency": m.p99_latency,
            "cpu_usage": m.cpu_usage, "memory_usage": m.memory_usage,
        }
        for m in metrics
    ]
