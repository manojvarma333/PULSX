"""Per-worker monitor query API (PRD section 32)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.worker import Worker

router = APIRouter(prefix="/experiments/{experiment_id}/workers", tags=["workers"])


@router.get("")
def list_workers(experiment_id: str, db: Session = Depends(get_db)) -> list[dict]:
    workers = db.query(Worker).filter(Worker.experiment_id == experiment_id).all()
    return [
        {
            "worker_id": w.worker_id, "language": w.language, "hostname": w.hostname,
            "status": w.status, "cpu_usage": w.cpu_usage, "memory_usage": w.memory_usage,
        }
        for w in workers
    ]
