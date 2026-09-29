import pytest

from replay.data_loader import DataLoader
from replay.models import MarketEvent


def _write(tmp_path, content: str):
    path = tmp_path / "data.csv"
    path.write_text(content)
    return path


def test_loads_events_with_sequence_numbers(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,100.00,10,B\n"
        "2,BTCUSD,100.50,5,S\n"
    )
    events = list(DataLoader().load(_write(tmp_path, content)))

    assert events == [
        MarketEvent(1, 1, "BTCUSD", 100.00, 10, "B"),
        MarketEvent(2, 2, "BTCUSD", 100.50, 5, "S"),
    ]


def test_raises_on_invalid_data_by_default(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,-100.00,10,B\n"
    )
    with pytest.raises(ValueError):
        list(DataLoader().load(_write(tmp_path, content)))


def test_skips_validation_when_disabled(tmp_path):
    content = (
        "timestamp,symbol,price,quantity,side\n"
        "1,BTCUSD,-100.00,10,B\n"
    )
    events = list(DataLoader(validate=False).load(_write(tmp_path, content)))
    assert len(events) == 1
