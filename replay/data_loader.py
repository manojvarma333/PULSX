"""Loads validated market-data CSV files as a lazy stream of MarketEvent records.

Used by the (future) replay engine so multi-million-row datasets are never fully
materialized in memory.
"""
from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from replay.models import MarketEvent
from replay.validator import validate_file

HEADER = ["timestamp", "symbol", "price", "quantity", "side"]


class DataLoader:
    """Streams `MarketEvent` records from a CSV file, assigning sequence numbers in order."""

    def __init__(self, validate: bool = True):
        self.validate = validate

    def load(self, path: str | Path) -> Iterator[MarketEvent]:
        path = Path(path)

        if self.validate:
            report = validate_file(path)
            if report.invalid_records > 0:
                raise ValueError(
                    f"{path} contains {report.invalid_records} invalid record(s); "
                    "run replay/validator.py for details or use DataLoader(validate=False) to skip."
                )

        with path.open("r", newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return
            if header != HEADER:
                f.seek(0)
                reader = csv.reader(f)

            sequence_number = 1
            for row in reader:
                yield MarketEvent.from_row(sequence_number, row)
                sequence_number += 1
