import numpy as np

from tools.generate_market_data import generate_records, write_csv, HEADER


def test_generate_records_reproducible():
    args = dict(
        events=500,
        symbols=5,
        price_min=10.0,
        price_max=1000.0,
        qty_min=1,
        qty_max=50,
        start_timestamp=1_000_000,
        interval=100,
        jitter=10,
        seed=7,
    )
    r1 = generate_records(**args)
    r2 = generate_records(**args)

    ts1, sym1, price1, qty1, side1 = r1
    ts2, sym2, price2, qty2, side2 = r2

    assert np.array_equal(ts1, ts2)
    assert sym1 == sym2
    assert np.array_equal(price1, price2)
    assert np.array_equal(qty1, qty2)
    assert np.array_equal(side1, side2)


def test_generate_records_ordering_and_ranges():
    timestamps, symbols, prices, quantities, sides = generate_records(
        events=1000,
        symbols=3,
        price_min=50.0,
        price_max=100.0,
        qty_min=5,
        qty_max=10,
        start_timestamp=0,
        interval=1,
        jitter=0,
        seed=1,
    )

    assert len(timestamps) == 1000
    # Strictly non-decreasing (interval > 0 with no jitter -> strictly increasing after first).
    assert np.all(np.diff(timestamps) >= 0)
    assert set(symbols) <= {"BTCUSD", "ETHUSD", "SOLUSD"}
    assert prices.min() >= 50.0 and prices.max() <= 100.0
    assert quantities.min() >= 5 and quantities.max() <= 10
    assert set(sides.tolist()) <= {"B", "S"}


def test_write_csv_produces_expected_row_count(tmp_path):
    timestamps, symbols, prices, quantities, sides = generate_records(
        events=50,
        symbols=2,
        price_min=1.0,
        price_max=2.0,
        qty_min=1,
        qty_max=2,
        start_timestamp=0,
        interval=1,
        jitter=0,
        seed=3,
    )
    output = tmp_path / "out.csv"
    written = write_csv(output, timestamps, symbols, prices, quantities, sides, seed=3)

    assert written == 50
    lines = output.read_text().splitlines()
    assert lines[0] == HEADER
    assert len(lines) == 51  # header + 50 rows
