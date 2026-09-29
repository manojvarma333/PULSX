from replay.models import MarketEvent
from replay.replay_engine import ReplayEngine, ReplayMode


def _events(n: int, interval: int = 1000) -> list[MarketEvent]:
    return [
        MarketEvent(sequence_number=i, timestamp=i * interval, symbol="BTCUSD", price=100.0, quantity=1, side="B")
        for i in range(1, n + 1)
    ]


def test_maximum_mode_sends_all_events_without_sleeping():
    sent = []
    engine = ReplayEngine(_events(200), publish=lambda e: sent.append(e) or True, mode=ReplayMode.MAXIMUM)
    stats = engine.run()

    assert stats.events_sent == 200
    assert stats.dropped_events == 0
    assert stats.connection_errors == 0
    assert len(sent) == 200
    assert stats.duration_seconds < 1.0  # should be near-instant


def test_accelerated_mode_respects_speed_multiplier():
    # 50 events spaced 100_000us (0.1s) apart -> ~5s at 1x, ~0.05s at 100x.
    engine = ReplayEngine(
        _events(50, interval=100_000),
        publish=lambda e: True,
        mode=ReplayMode.ACCELERATED,
        speed_multiplier=100.0,
    )
    stats = engine.run()

    assert stats.events_sent == 50
    assert stats.duration_seconds < 1.0


def test_dropped_and_error_events_are_counted():
    outcomes = iter([True, False, True])

    def flaky_publish(event):
        result = next(outcomes, None)
        if result is None:
            raise ConnectionError("boom")
        return result

    engine = ReplayEngine(_events(3), publish=flaky_publish, mode=ReplayMode.MAXIMUM)
    stats = engine.run()

    assert stats.events_sent == 2
    assert stats.dropped_events == 1
    assert stats.connection_errors == 0


def test_connection_errors_are_counted_and_do_not_stop_replay():
    def always_fails(event):
        raise OSError("network down")

    engine = ReplayEngine(_events(5), publish=always_fails, mode=ReplayMode.MAXIMUM)
    stats = engine.run()

    assert stats.connection_errors == 5
    assert stats.events_sent == 0


def test_rejects_non_positive_speed_multiplier():
    import pytest

    with pytest.raises(ValueError):
        ReplayEngine(_events(1), publish=lambda e: True, mode=ReplayMode.ACCELERATED, speed_multiplier=0)
