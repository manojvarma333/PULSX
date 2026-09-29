"""Strategy 5 -- Failure Simulation: intentionally fails at a configurable rate."""
from __future__ import annotations

import random

from replay.models import MarketEvent
from strategies.base import BaseStrategy


class FailureSimulationStrategy(BaseStrategy):
    name = "failure"

    def __init__(self, failure_probability: float = 0.05, seed: int | None = None):
        if not 0.0 <= failure_probability <= 1.0:
            raise ValueError("failure_probability must be between 0 and 1")
        self.failure_probability = failure_probability
        self._rng = random.Random(seed)

    def process(self, event: MarketEvent) -> dict:
        if self._rng.random() < self.failure_probability:
            raise RuntimeError(f"simulated failure processing sequence {event.sequence_number}")
        return {"symbol": event.symbol, "price": event.price}
