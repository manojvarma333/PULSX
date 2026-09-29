"""Strategy registry -- maps a config string (e.g. "moving_average") to an implementation."""
from __future__ import annotations

from strategies.base import BaseStrategy
from strategies.cpu_stress import CpuStressStrategy
from strategies.failure import FailureSimulationStrategy
from strategies.moving_average import MovingAverageStrategy
from strategies.passthrough import PassThroughStrategy
from strategies.statistics import StatisticsStrategy

STRATEGIES: dict[str, type[BaseStrategy]] = {
    "passthrough": PassThroughStrategy,
    "moving_average": MovingAverageStrategy,
    "statistics": StatisticsStrategy,
    "cpu_stress": CpuStressStrategy,
    "failure": FailureSimulationStrategy,
}


def create_strategy(name: str, **kwargs) -> BaseStrategy:
    try:
        cls = STRATEGIES[name]
    except KeyError as exc:
        raise ValueError(f"unknown strategy: {name!r}; available: {sorted(STRATEGIES)}") from exc
    return cls(**kwargs)
