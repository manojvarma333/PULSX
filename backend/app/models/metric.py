from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.session import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    worker_id: Mapped[str] = mapped_column(String(100))
    event_count: Mapped[int] = mapped_column(Integer)
    throughput: Mapped[float] = mapped_column(Float)
    avg_latency: Mapped[float] = mapped_column(Float)
    p95_latency: Mapped[float] = mapped_column(Float)
    p99_latency: Mapped[float] = mapped_column(Float)
    cpu_usage: Mapped[float] = mapped_column(Float)
    memory_usage: Mapped[float] = mapped_column(Float)

    experiment: Mapped["Experiment"] = relationship(back_populates="metrics")
