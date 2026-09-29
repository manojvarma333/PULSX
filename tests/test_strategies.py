from strategies import create_strategy
from strategies.cpu_stress import CpuStressStrategy
from strategies.failure import FailureSimulationStrategy
from strategies.moving_average import MovingAverageStrategy
from strategies.passthrough import PassThroughStrategy
from strategies.statistics import StatisticsStrategy
from replay.models import MarketEvent


def _event(seq=1, symbol="BTCUSD", price=100.0):
    return MarketEvent(seq, seq * 1000, symbol, price, 10, "B")


def test_passthrough_returns_symbol_and_price():
    strat = PassThroughStrategy()
    result = strat.process(_event(price=123.45))
    assert result == {"symbol": "BTCUSD", "price": 123.45}


def test_moving_average_rolls_over_window():
    strat = MovingAverageStrategy(window=2)
    strat.process(_event(1, price=10.0))
    strat.process(_event(2, price=20.0))
    result = strat.process(_event(3, price=30.0))
    # Window of 2 -> average of last two prices (20, 30).
    assert result["moving_average"] == 25.0
    assert result["window_size"] == 2


def test_statistics_matches_known_values():
    strat = StatisticsStrategy()
    for price in (2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0):
        result = strat.process(_event(price=price))
    assert result["count"] == 8
    assert round(result["mean"], 4) == 5.0
    assert round(result["variance"], 4) == 4.0  # population variance of this classic example


def test_cpu_stress_runs_configured_iterations():
    strat = CpuStressStrategy(iterations=100)
    result = strat.process(_event())
    assert "checksum" in result


def test_failure_strategy_is_deterministic_with_seed():
    strat = FailureSimulationStrategy(failure_probability=1.0, seed=1)
    try:
        strat.process(_event())
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass

    strat_never = FailureSimulationStrategy(failure_probability=0.0, seed=1)
    result = strat_never.process(_event())
    assert result["symbol"] == "BTCUSD"


def test_create_strategy_by_name():
    strat = create_strategy("moving_average", window=5)
    assert isinstance(strat, MovingAverageStrategy)
    assert strat.window == 5
