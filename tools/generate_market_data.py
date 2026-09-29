#!/usr/bin/env python3
"""Synthetic market-data generator (PRD section 8).

Produces a normalized CSV (timestamp,symbol,price,quantity,side) with a reproducible
random seed. Supports optional error injection (--duplicate-rate / --invalid-rate) to
produce datasets that exercise the validator.

Example:
    python tools/generate_market_data.py --events 1000000 --symbols 10 --seed 42
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

# Recognizable instrument pool; extended with SYM{n} if more symbols are requested.
_SYMBOL_POOL = [
    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD", "LTCUSD", "BNBUSD",
    "AVAXUSD", "DOTUSD", "MATICUSD", "LINKUSD", "ATOMUSD", "UNIUSD",
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA",
]

HEADER = "timestamp,symbol,price,quantity,side"


def build_symbol_pool(num_symbols: int) -> list[str]:
    if num_symbols <= len(_SYMBOL_POOL):
        return _SYMBOL_POOL[:num_symbols]
    extra = [f"SYM{i}" for i in range(num_symbols - len(_SYMBOL_POOL))]
    return _SYMBOL_POOL + extra


def generate_records(
    events: int,
    symbols: int,
    price_min: float,
    price_max: float,
    qty_min: int,
    qty_max: int,
    start_timestamp: int,
    interval: int,
    jitter: int,
    seed: int,
) -> tuple[np.ndarray, list[str], np.ndarray, np.ndarray, np.ndarray]:
    """Generate arrays for all fields. Returns (timestamps, symbol_names, prices, quantities, sides)."""
    if events <= 0:
        raise ValueError("events must be > 0")
    if symbols <= 0:
        raise ValueError("symbols must be > 0")
    if price_min <= 0 or price_max <= price_min:
        raise ValueError("price_max must be > price_min > 0")
    if qty_min <= 0 or qty_max < qty_min:
        raise ValueError("qty_max must be >= qty_min > 0")
    if interval < 0 or jitter < 0:
        raise ValueError("interval and jitter must be >= 0")

    rng = np.random.default_rng(seed)

    pool = build_symbol_pool(symbols)
    symbol_idx = rng.integers(0, symbols, size=events)
    symbol_names = np.array(pool, dtype=object)[symbol_idx]

    # Strictly increasing timestamps preserve event ordering within the stream.
    gaps = np.full(events, interval, dtype=np.int64)
    if jitter > 0:
        gaps = gaps + rng.integers(0, jitter + 1, size=events, dtype=np.int64)
    gaps[0] = 0
    timestamps = start_timestamp + np.cumsum(gaps)

    prices = np.round(rng.uniform(price_min, price_max, size=events), 2)
    quantities = rng.integers(qty_min, qty_max + 1, size=events)
    sides = rng.choice(np.array(["B", "S"], dtype=object), size=events)

    return timestamps, symbol_names.tolist(), prices, quantities, sides


def _inject_errors(
    lines: list[str],
    duplicate_rate: float,
    invalid_rate: float,
    rng: np.random.Generator,
) -> list[str]:
    """Mutate a copy of generated CSV lines to include duplicates / malformed rows."""
    if duplicate_rate <= 0 and invalid_rate <= 0:
        return lines

    n = len(lines)
    out = list(lines)

    if duplicate_rate > 0:
        num_dupes = min(n, int(n * duplicate_rate))
        for _ in range(num_dupes):
            src = rng.integers(0, n)
            dst = rng.integers(0, n)
            out[dst] = out[src]

    if invalid_rate > 0:
        num_invalid = min(n, int(n * invalid_rate))
        corruptions = [
            lambda row: row[:-1] + ("X",),  # invalid side
            lambda row: (row[0], row[1], "-1.00", row[3], row[4]),  # invalid price
            lambda row: (row[0], row[1], row[2], "0", row[4]),  # invalid quantity
            lambda row: (row[0], row[1], "", row[3], row[4]),  # missing field
            lambda row: row[:-1],  # malformed (missing column)
        ]
        # Unique indices so a corruption never applies twice to an already-shortened row.
        indices = rng.choice(n, size=num_invalid, replace=False)
        for idx in indices:
            fields = tuple(out[idx].split(","))
            corrupt = corruptions[int(rng.integers(0, len(corruptions)))]
            out[idx] = ",".join(corrupt(fields))

    return out


def write_csv(
    output_path: Path,
    timestamps: np.ndarray,
    symbol_names: list[str],
    prices: np.ndarray,
    quantities: np.ndarray,
    sides: np.ndarray,
    duplicate_rate: float = 0.0,
    invalid_rate: float = 0.0,
    seed: int = 0,
    chunk_size: int = 200_000,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events = len(timestamps)
    rng = np.random.default_rng(seed)

    with output_path.open("w", newline="") as f:
        f.write(HEADER + "\n")
        for start in range(0, events, chunk_size):
            end = min(start + chunk_size, events)
            lines = [
                f"{timestamps[i]},{symbol_names[i]},{prices[i]:.2f},{quantities[i]},{sides[i]}"
                for i in range(start, end)
            ]
            lines = _inject_errors(lines, duplicate_rate, invalid_rate, rng)
            f.write("\n".join(lines) + "\n")
    return events


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic PulseX market data.")
    parser.add_argument("--events", type=int, default=1000, help="Number of events to generate.")
    parser.add_argument("--symbols", type=int, default=10, help="Number of distinct instruments.")
    parser.add_argument("--price-min", type=float, default=100.0)
    parser.add_argument("--price-max", type=float, default=50000.0)
    parser.add_argument("--qty-min", type=int, default=1)
    parser.add_argument("--qty-max", type=int, default=1000)
    parser.add_argument(
        "--start-timestamp",
        type=int,
        default=None,
        help="Starting timestamp (microseconds). Defaults to current time.",
    )
    parser.add_argument("--interval", type=int, default=1000, help="Base gap between events (microseconds).")
    parser.add_argument("--jitter", type=int, default=0, help="Extra random gap added on top of --interval.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed; guarantees reproducibility.")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path.")
    parser.add_argument("--duplicate-rate", type=float, default=0.0, help="Fraction of rows duplicated (testing).")
    parser.add_argument("--invalid-rate", type=float, default=0.0, help="Fraction of rows corrupted (testing).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    start_timestamp = args.start_timestamp if args.start_timestamp is not None else int(time.time() * 1_000_000)
    output = Path(args.output) if args.output else Path("data/generated") / f"market_data_{args.events}.csv"

    timestamps, symbol_names, prices, quantities, sides = generate_records(
        events=args.events,
        symbols=args.symbols,
        price_min=args.price_min,
        price_max=args.price_max,
        qty_min=args.qty_min,
        qty_max=args.qty_max,
        start_timestamp=start_timestamp,
        interval=args.interval,
        jitter=args.jitter,
        seed=args.seed,
    )
    written = write_csv(
        output,
        timestamps,
        symbol_names,
        prices,
        quantities,
        sides,
        duplicate_rate=args.duplicate_rate,
        invalid_rate=args.invalid_rate,
        seed=args.seed,
    )
    print(f"Generated {written:,} events -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
