#!/usr/bin/env python3
"""Benchmark Engine (PRD sections 21-22, 44, component #15): runs the same dataset
through multiple configurations and records REAL measured results via the
ExperimentController -- never fabricated (PRD sections 34, 50).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from itertools import product

from experiment_controller.config import ExperimentConfig
from experiment_controller.controller import ExperimentController, ExperimentResult


@dataclass
class BenchmarkCase:
    protocol: str = "json"
    worker_count: int = 1
    strategy: str = "passthrough"
    worker_language: str = "python"


class BenchmarkRunner:
    def __init__(self, dataset_file: str, worker_launch_mode: str = "thread"):
        self.dataset_file = dataset_file
        self.worker_launch_mode = worker_launch_mode

    def run_case(self, case: BenchmarkCase, name: str | None = None) -> ExperimentResult:
        config = ExperimentConfig(
            name=name or f"{case.protocol}-{case.worker_language}-{case.worker_count}w-{case.strategy}",
            dataset_file=self.dataset_file,
            protocol=case.protocol,
            worker_language=case.worker_language,
            worker_count=case.worker_count,
            strategy=case.strategy,
            replay_mode="maximum",
            heartbeat_interval=1.0,
            completion_timeout=120.0,
        )
        controller = ExperimentController(config, worker_launch_mode=self.worker_launch_mode)
        return controller.run()

    def run_matrix(self, cases: list[BenchmarkCase]) -> list[ExperimentResult]:
        return [self.run_case(case) for case in cases]


def default_python_matrix() -> list[BenchmarkCase]:
    """PRD section 22 matrix, restricted to Python workers (C++ requires a built binary
    -- see benchmark.sh / experiment_controller for how to include cpp cases once built)."""
    return [
        BenchmarkCase(protocol=protocol, worker_count=worker_count, strategy="passthrough")
        for protocol, worker_count in product(("json", "binary"), (1, 2, 4))
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a PulseX benchmark case.")
    parser.add_argument("--dataset", required=True, help="Path to a validated market-data CSV.")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--protocol", default="json", choices=["json", "binary"])
    parser.add_argument("--language", default="python", choices=["python", "cpp"])
    parser.add_argument("--strategy", default="passthrough",
                         choices=["passthrough", "moving_average", "statistics", "cpu_stress", "failure"])
    parser.add_argument("--worker-launch-mode", default="thread", choices=["thread", "process"])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = BenchmarkRunner(args.dataset, worker_launch_mode=args.worker_launch_mode)
    case = BenchmarkCase(protocol=args.protocol, worker_count=args.workers, strategy=args.strategy,
                          worker_language=args.language)
    result = runner.run_case(case)

    summary = result.aggregator_summary
    e2e = summary["end_to_end_latency_ms"]
    print("Experiment completed\n")
    print(f"Events:\n{result.replay_stats['events_sent']:,}\n")
    print(f"Duration:\n{result.replay_stats['replay_duration_seconds']:.4f}s\n")
    print(f"Throughput:\n{result.replay_stats['events_per_sec']:.2f} events/sec\n")
    print(f"Average latency:\n{e2e['avg']:.4f} ms\n")
    print(f"P95:\n{e2e['p95']:.4f} ms\n")
    print(f"P99:\n{e2e['p99']:.4f} ms\n")
    print(f"Missing events:\n{len(summary['missing_events'])}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
