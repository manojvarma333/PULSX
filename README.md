# PulseX

Low-latency market-data replay & distributed simulation engine — a local research/systems-engineering
platform for studying networking, serialization, concurrency, and fault tolerance trade-offs.

> PulseX is **not** a trading system. Market data is only a synthetic workload used to study
> distributed-systems performance (throughput, latency, reliability, recovery time).

## Status

All 14 PRD phases are implemented:

- [x] Phase 1 — Market data generator + validator + data loader (`tools/`, `replay/`)
- [x] Phase 2 — Python replay engine (`replay/replay_engine.py`)
- [x] Phase 3 — TCP event server + wire protocol (`event_server/`)
- [x] Phase 4 — Python worker (`workers/python/worker.py`)
- [x] Phase 5 — C++ worker (`workers/cpp/`) — **written but unverified: no C++ compiler or
      working Docker daemon was available in the environment this was built in. Build and
      run it (`workers/cpp/README.md`) before relying on it, and report any build errors.**
- [x] Phase 6 — Multiple workers (round-robin distribution, tested with 3 concurrent workers)
- [x] Phase 7 — Metrics engine: throughput, latency P50/P95/P99, CPU/memory (`metrics_engine/`)
- [x] Phase 8 — Failure detection + recovery (`event_server/recovery.py`, `aggregator/`)
- [x] Phase 9 — PostgreSQL storage + FastAPI backend (`backend/`, SQLite for local dev/tests)
- [x] Phase 10 — React dashboard (`frontend/`, Vite + TypeScript + Recharts)
- [x] Phase 11 — Docker Compose (`docker-compose.yml`, `Dockerfile`, `workers/cpp/Dockerfile`)
- [x] Phase 12 — Benchmark engine (`benchmark/`)
- [x] Phase 13 — Experimental comparison support (protocol/worker-count/strategy matrix;
      Python-vs-C++ comparison requires building the C++ worker first)
- [x] Phase 14 — Documentation (`docs/architecture.md`, `docs/protocol.md`,
      `docs/benchmarking.md`, `docs/experiments.md`)

All numbers produced by this system (throughput, latency, etc.) come from real measured
experiment runs — nothing is hardcoded (PRD sections 34, 50).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt -r backend/requirements.txt
pytest                                         # 60+ tests, all in-process/real-TCP, no Docker needed

python tools/generate_market_data.py --events 100000 --symbols 10 --seed 42
python replay/validator.py data/generated/market_data_100000.csv

uvicorn backend.app.main:app --reload          # backend API on :8000
cd frontend && npm install && npm run dev      # dashboard on :5173
```

Or the whole stack via Docker:

```bash
cp .env.example .env
docker compose up --build
```

Run a benchmark case directly:

```bash
python -m benchmark.runner --dataset data/generated/market_data_100000.csv \
    --workers 4 --protocol binary --language python --strategy moving_average
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — component map and event data flow
- [`docs/protocol.md`](docs/protocol.md) — wire format (framing, JSON + binary event layout)
- [`docs/experiments.md`](docs/experiments.md) — running experiments, worker launch modes, chaos testing
- [`docs/benchmarking.md`](docs/benchmarking.md) — comparison matrix, reports

## Project layout

```
tools/               synthetic market-data generator
replay/               validator, data loader, replay engine
event_server/         TCP server, wire protocol, connection manager, distributor, recovery
workers/python/       Python worker
workers/cpp/          C++17 worker (Docker-buildable; see its README)
strategies/           simulation workloads (passthrough, moving_average, statistics, cpu_stress, failure)
metrics_engine/       latency percentiles, throughput, CPU/memory sampling
aggregator/           result aggregation, missing-sequence detection
experiment_controller/  orchestrates one full experiment run end-to-end
benchmark/            runs comparison matrices, produces reports
backend/              FastAPI + SQLAlchemy (Postgres/SQLite) experiment metadata API
frontend/             React + Vite + TypeScript dashboard
scripts/              setup/start/stop/generate_data/benchmark/health_check shell scripts
docs/                 architecture, protocol, benchmarking, experiments docs
tests/                pytest suite (Python side; C++ has its own tests in workers/cpp/tests)
```

## Requirements

```
pip install -r requirements.txt -r backend/requirements.txt
```

## Tests

```
pytest
```

