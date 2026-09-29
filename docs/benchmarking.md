# Benchmarking PulseX

Real, actual-measurement-only benchmarking (PRD sections 21-22, 34, 44, 50). Nothing in
`benchmark/` fabricates or hardcodes results -- every number comes from an
`ExperimentController` run against a real (in-process or subprocess) worker.

## Quick single-case benchmark

```
python -m benchmark.runner --dataset data/generated/market_data_100000.csv \
    --workers 4 --protocol binary --language python --strategy moving_average
```

Or via the shell wrapper (spawns real worker subprocesses):

```
./scripts/benchmark.sh --events 1000000 --workers 4 --protocol binary --language cpp
```

## Comparison matrix

```python
from benchmark.runner import BenchmarkRunner, default_python_matrix
from benchmark.analyzer import compare, format_table

runner = BenchmarkRunner("data/generated/market_data_100000.csv")
results = runner.run_matrix(default_python_matrix())
print(format_table(compare(results)))
```

This produces a Markdown table like:

| name | protocol | worker_language | worker_count | throughput_events_per_sec | p95_latency_ms |
|---|---|---|---|---|---|
| json-python-1w-passthrough | json | python | 1 | *(actual)* | *(actual)* |
| binary-python-4w-passthrough | binary | python | 4 | *(actual)* | *(actual)* |

All `*(actual)*` values are real measurements from that run on your machine -- they will
differ from any other machine and must always be reported alongside hardware/OS/dataset
size/worker count/protocol/language/config (PRD section 50).

## C++ vs Python

`worker_language="cpp"` requires a prebuilt binary (`workers/cpp/build/pulsex_cpp_worker`,
see `workers/cpp/README.md`) and `worker_launch_mode="process"` (C++ workers are always
spawned as real OS subprocesses, never in-process threads). `ExperimentController` raises
a clear `RuntimeError` if the binary is missing rather than silently skipping the case.

## Reports

`benchmark/report.py` writes a JSON + Markdown summary per experiment (PRD section 48),
including reproducibility metadata (`system_info`, `config`, experiment id, timestamps)
so results can be attributed to the exact hardware/software they were measured on.
