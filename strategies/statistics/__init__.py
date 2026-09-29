"""Strategy 3 -- Statistical Calculation: mean/variance/std-dev per symbol.

Uses Welford's online algorithm so it runs in O(1) time/memory per event.
"""
from __future__ import annotations

from replay.models import MarketEvent
from strategies.base import BaseStrategy


class StatisticsStrategy(BaseStrategy):
    name = "statistics"

    def __init__(self):
        self._state: dict[str, tuple[int, float, float]] = {}  # symbol -> (n, mean, M2)

    def process(self, event: MarketEvent) -> dict:
        n, mean, m2 = self._state.get(event.symbol, (0, 0.0, 0.0))
        n += 1
        delta = event.price - mean
        mean += delta / n
        m2 += delta * (event.price - mean)
        variance = m2 / n if n > 0 else 0.0
        self._state[event.symbol] = (n, mean, m2)
        return {
            "symbol": event.symbol,
            "mean": mean,
            "variance": variance,
            "std_dev": variance ** 0.5,
            "count": n,
        }
