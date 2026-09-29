"""Optional, small-scale event storage (PRD section 27 schema). NOT used for bulk
experiment replay data -- the PRD explicitly warns against storing every event in
Postgres for large datasets. Reserved for e.g. storing a handful of sample/debug rows.
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class SampleEvent(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"))
    sequence_number: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[int] = mapped_column(Integer)
    symbol: Mapped[str] = mapped_column(String(20))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    side: Mapped[str] = mapped_column(String(1))
