"""Strategy 1 -- Pass Through: minimal processing, used to measure networking overhead."""
from __future__ import annotations

from replay.models import MarketEvent
from strategies.base import BaseStrategy


class PassThroughStrategy(BaseStrategy):
    name = "passthrough"

    def process(self, event: MarketEvent) -> dict:
        return {"symbol": event.symbol, "price": event.price}
