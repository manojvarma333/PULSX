from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.session import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID from ExperimentController
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    dataset: Mapped[str] = mapped_column(String(500))
    protocol: Mapped[str] = mapped_column(String(20))
    worker_language: Mapped[str] = mapped_column(String(20))
    worker_count: Mapped[int] = mapped_column(Integer)
    strategy: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")

    workers: Mapped[list["Worker"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    metrics: Mapped[list["Metric"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    failures: Mapped[list["Failure"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
