"""Experiment report generation (PRD section 48): JSON + Markdown, actual measured
values only -- never hardcoded (PRD sections 34, 50)."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from experiment_controller.controller import ExperimentResult


def to_markdown(result: ExperimentResult) -> str:
    summary = result.aggregator_summary
    e2e = summary["end_to_end_latency_ms"]
    successful = sum(w["events_processed"] for w in summary["workers"].values())
    failed = sum(w["events_failed"] for w in summary["workers"].values())

    return f"""# Experiment Summary

**Dataset:** {result.config['dataset_file']}
**Workers:** {result.config['worker_count']} ({result.config['worker_language']})
**Protocol:** {result.config['protocol']}
**Strategy:** {result.config['strategy']}

**Total Events:** {result.replay_stats['events_sent']}
**Successful:** {successful}
**Failed:** {failed}

**Throughput:** {result.replay_stats['events_per_sec']:.2f} events/sec
**Average Latency:** {e2e['avg']:.4f} ms
**P95:** {e2e['p95']:.4f} ms
**P99:** {e2e['p99']:.4f} ms

**Failures:** {len(result.failures)}
**Missing Events:** {len(summary['missing_events'])}

_Generated {result.finished_at} on {result.system_info['os']} \
({result.system_info['cpu_cores']} cores, Python {result.system_info['python_version']})._
"""


def write_report(result: ExperimentResult, output_dir: str) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{result.experiment_id}.json"
    md_path = out_dir / f"{result.experiment_id}.md"
    json_path.write_text(json.dumps(asdict(result), indent=2))
    md_path.write_text(to_markdown(result))
    return json_path, md_path
