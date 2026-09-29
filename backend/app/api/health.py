"""Health checks (PRD section 41)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    checks = {"backend": "ok"}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - health checks must never raise
        checks["database"] = f"error: {exc}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "healthy" if healthy else "unhealthy", "checks": checks}
