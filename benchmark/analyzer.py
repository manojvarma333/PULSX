"""Builds a comparison matrix from real ExperimentResult objects (PRD sections 22, 34)."""
from __future__ import annotations

from experiment_controller.controller import ExperimentResult

_COLUMNS = [
    "name", "protocol", "worker_language", "worker_count", "strategy", "events",
    "duration_seconds", "throughput_events_per_sec", "avg_latency_ms", "p95_latency_ms",
    "p99_latency_ms", "missing_events",
]


def compare(results: list[ExperimentResult]) -> list[dict]:
    rows = []
    for r in results:
        summary = r.aggregator_summary
        e2e = summary["end_to_end_latency_ms"]
        rows.append({
            "name": r.name,
            "protocol": r.config["protocol"],
            "worker_language": r.config["worker_language"],
            "worker_count": r.config["worker_count"],
            "strategy": r.config["strategy"],
            "events": r.replay_stats["events_sent"],
            "duration_seconds": round(r.replay_stats["replay_duration_seconds"], 4),
            "throughput_events_per_sec": round(r.replay_stats["events_per_sec"], 2),
            "avg_latency_ms": round(e2e["avg"], 4),
            "p95_latency_ms": round(e2e["p95"], 4),
            "p99_latency_ms": round(e2e["p99"], 4),
            "missing_events": len(summary["missing_events"]),
        })
    return rows


def format_table(rows: list[dict]) -> str:
    if not rows:
        return "(no results)"
    lines = ["| " + " | ".join(_COLUMNS) + " |", "| " + " | ".join("---" for _ in _COLUMNS) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[c]) for c in _COLUMNS) + " |")
    return "\n".join(lines)
