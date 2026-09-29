from metrics_engine.latency import compute_latency_stats
from metrics_engine.throughput import events_per_second


def test_latency_stats_basic():
    stats = compute_latency_stats([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert stats.count == 10
    assert stats.minimum == 1
    assert stats.maximum == 10
    assert stats.average == 5.5
    assert stats.median == 5.5


def test_latency_stats_empty():
    stats = compute_latency_stats([])
    assert stats.count == 0
    assert stats.as_dict()["p95"] == 0.0


def test_latency_percentiles_monotonic():
    stats = compute_latency_stats(list(range(1, 101)))
    assert stats.median <= stats.p95 <= stats.p99 <= stats.maximum


def test_events_per_second():
    assert events_per_second(1000, 2.0) == 500.0
    assert events_per_second(1000, 0) == 1000.0
