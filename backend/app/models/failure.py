from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.session import Base


class Failure(Base):
    __tablename__ = "failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    worker_id: Mapped[str] = mapped_column(String(100))
    failure_type: Mapped[str] = mapped_column(String(50), default="worker_offline")
    detected_at: Mapped[datetime] = mapped_column(DateTime)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recovery_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    experiment: Mapped["Experiment"] = relationship(back_populates="failures")
