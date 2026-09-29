"""Common interface for simulation strategies (PRD section 16)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from replay.models import MarketEvent


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def process(self, event: MarketEvent) -> dict:
        """Process one event and return a small JSON-serializable result payload."""
