"""Shared data model for a single market event flowing through PulseX."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketEvent:
    """One normalized market-data record (see PRD section 7: Market Data Format)."""

    sequence_number: int
    timestamp: int
    symbol: str
    price: float
    quantity: int
    side: str  # "B" or "S"

    @staticmethod
    def from_row(sequence_number: int, row: list[str]) -> "MarketEvent":
        timestamp_str, symbol, price_str, quantity_str, side = row
        return MarketEvent(
            sequence_number=sequence_number,
            timestamp=int(timestamp_str),
            symbol=symbol,
            price=float(price_str),
            quantity=int(quantity_str),
            side=side,
        )
