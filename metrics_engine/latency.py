"""Latency statistics (PRD section 18). Never rely on average alone -- always compute
percentiles too. Pure-Python (no numpy) so it stays cheap to import in worker processes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class LatencyStats:
    count: int
    minimum: float
    average: float
    median: float
    p95: float
    p99: float
    maximum: float

    def as_dict(self) -> dict:
        return {
            "count": self.count,
            "min": self.minimum,
            "avg": self.average,
            "median": self.median,
            "p95": self.p95,
            "p99": self.p99,
            "max": self.maximum,
        }


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (matches numpy's default 'linear' method)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = p / 100 * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def compute_latency_stats(values: list[float]) -> LatencyStats:
    if not values:
        return LatencyStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    ordered = sorted(values)
    n = len(ordered)
    return LatencyStats(
        count=n,
        minimum=ordered[0],
        average=sum(ordered) / n,
        median=_percentile(ordered, 50),
        p95=_percentile(ordered, 95),
        p99=_percentile(ordered, 99),
        maximum=ordered[-1],
    )
