"""Strategy 4 -- CPU Stress: configurable computational workload."""
from __future__ import annotations

from replay.models import MarketEvent
from strategies.base import BaseStrategy


class CpuStressStrategy(BaseStrategy):
    name = "cpu_stress"

    def __init__(self, iterations: int = 10_000):
        if iterations < 0:
            raise ValueError("iterations must be >= 0")
        self.iterations = iterations

    def process(self, event: MarketEvent) -> dict:
        checksum = 0.0
        for i in range(self.iterations):
            checksum += (event.price * i) % 97.0
        return {"symbol": event.symbol, "checksum": checksum}
