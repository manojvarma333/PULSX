"""Failure/recovery query API (PRD section 23-24)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.session import get_db
from backend.app.models.failure import Failure

router = APIRouter(prefix="/experiments/{experiment_id}/failures", tags=["failures"])


@router.get("")
def list_failures(experiment_id: str, db: Session = Depends(get_db)) -> list[dict]:
    failures = db.query(Failure).filter(Failure.experiment_id == experiment_id).all()
    return [
        {
            "worker_id": f.worker_id, "failure_type": f.failure_type,
            "detected_at": f.detected_at.isoformat() if f.detected_at else None,
            "recovered_at": f.recovered_at.isoformat() if f.recovered_at else None,
            "recovery_time": f.recovery_time,
        }
        for f in failures
    ]
