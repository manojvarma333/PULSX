#!/usr/bin/env python3
"""Market data validator (PRD section 9).

Streams a CSV file row by row (no full-file load, so multi-million-row datasets stay
memory-bounded) and reports data-quality issues. Invalid rows are always reported with
their line number and reason -- never silently dropped.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

EXPECTED_FIELDS = 5
VALID_SIDES = {"B", "S"}


@dataclass
class InvalidRecord:
    line_number: int
    reason: str
    raw: str


@dataclass
class ValidationReport:
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicates: int = 0
    out_of_order_events: int = 0
    missing_values: int = 0
    errors: list[InvalidRecord] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        return d

    def print_summary(self) -> None:
        print("Total Records:      ", self.total_records)
        print("Valid Records:      ", self.valid_records)
        print("Invalid Records:    ", self.invalid_records)
        print("Duplicates:         ", self.duplicates)
        print("Out-of-order Events:", self.out_of_order_events)
        print("Missing Values:     ", self.missing_values)


def validate_file(path: Path) -> ValidationReport:
    report = ValidationReport()
    seen_rows: set[str] = set()
    last_timestamp: int | None = None

    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return report
        if header != ["timestamp", "symbol", "price", "quantity", "side"]:
            # Not a header row; treat as data by rewinding.
            f.seek(0)
            reader = csv.reader(f)

        for line_number, row in enumerate(reader, start=2):
            report.total_records += 1
            is_invalid = False

            if len(row) != EXPECTED_FIELDS:
                report.errors.append(InvalidRecord(line_number, "malformed record (wrong field count)", ",".join(row)))
                report.invalid_records += 1
                continue

            timestamp_str, symbol, price_str, quantity_str, side = row
            raw = ",".join(row)

            if any(field_value == "" for field_value in row):
                report.missing_values += 1
                report.errors.append(InvalidRecord(line_number, "missing field", raw))
                is_invalid = True

            timestamp: int | None = None
            if timestamp_str != "":
                try:
                    timestamp = int(timestamp_str)
                except ValueError:
                    report.errors.append(InvalidRecord(line_number, "invalid timestamp format", raw))
                    is_invalid = True

            if price_str != "":
                try:
                    if float(price_str) <= 0:
                        raise ValueError
                except ValueError:
                    report.errors.append(InvalidRecord(line_number, "invalid price", raw))
                    is_invalid = True

            if quantity_str != "":
                try:
                    if int(quantity_str) <= 0:
                        raise ValueError
                except ValueError:
                    report.errors.append(InvalidRecord(line_number, "invalid quantity", raw))
                    is_invalid = True

            if side != "" and side not in VALID_SIDES:
                report.errors.append(InvalidRecord(line_number, "invalid side", raw))
                is_invalid = True

            if timestamp is not None:
                if last_timestamp is not None and timestamp < last_timestamp:
                    report.out_of_order_events += 1
                last_timestamp = timestamp

            if raw in seen_rows:
                report.duplicates += 1
            else:
                seen_rows.add(raw)

            if is_invalid:
                report.invalid_records += 1
            else:
                report.valid_records += 1

    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PulseX market data CSV files.")
    parser.add_argument("file", type=str, help="Path to the CSV file to validate.")
    parser.add_argument("--json", type=str, default=None, help="Optional path to also write the report as JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        return 1

    report = validate_file(path)
    report.print_summary()

    if args.json:
        Path(args.json).write_text(json.dumps(report.as_dict(), indent=2))

    return 0 if report.invalid_records == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
