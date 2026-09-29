"""Strategy 2 -- Moving Average: maintains a rolling per-symbol price average."""
from __future__ import annotations

from collections import defaultdict, deque

from replay.models import MarketEvent
from strategies.base import BaseStrategy


class MovingAverageStrategy(BaseStrategy):
    name = "moving_average"

    def __init__(self, window: int = 20):
        if window <= 0:
            raise ValueError("window must be > 0")
        self.window = window
        self._prices: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))

    def process(self, event: MarketEvent) -> dict:
        prices = self._prices[event.symbol]
        prices.append(event.price)
        return {
            "symbol": event.symbol,
            "moving_average": sum(prices) / len(prices),
            "window_size": len(prices),
        }
