# PulseX Architecture

See the top-level README for the phase checklist. This document describes how the pieces
fit together (PRD section 5).

```
Replay Engine --(publish)--> Event Distributor --TCP--> Workers (Python/C++)
                                    |                         |
                             Connection Manager         Strategy + Metrics
                                    |                         |
                             Recovery Manager <--(RESULT)-- Result Aggregator
                                    |
                              FastAPI Backend --> PostgreSQL
                                    |
                              React Dashboard
```

## Components and where they live

| PRD component            | Code location                                  |
|---------------------------|------------------------------------------------|
| Market Data Generator      | `tools/generate_market_data.py`                |
| Market Data Validator      | `replay/validator.py`                          |
| Data Loader                | `replay/data_loader.py`, `replay/models.py`    |
| Replay Engine               | `replay/replay_engine.py`                      |
| TCP Event Server            | `event_server/server.py`                       |
| Message Protocol            | `event_server/protocol.py`                     |
| Connection Manager           | `event_server/connection_manager.py`           |
| Event Distributor            | `event_server/distributor.py`                  |
| Recovery Manager              | `event_server/recovery.py`                     |
| Result Aggregator             | `aggregator/result_aggregator.py`              |
| Python Worker                 | `workers/python/worker.py`                     |
| C++ Worker                    | `workers/cpp/`                                 |
| Simulation Strategies          | `strategies/`                                  |
| Metrics Engine                  | `metrics_engine/`                              |
| Experiment Controller             | `experiment_controller/`                       |
| Benchmark Engine                   | `benchmark/`                                   |
| PostgreSQL / API backend            | `backend/`                                     |
| React Monitoring Dashboard            | `frontend/`                                    |

## Data flow per event

1. `ReplayEngine` reads a `MarketEvent` from `DataLoader` and calls `publish()`.
2. `EventDistributor.publish()` round-robins to an ONLINE worker and records the dispatch
   in `ResultAggregator` (T1 = `dispatched_at_ns`, embedded in the wire message).
3. The worker's `FrameReader` reassembles the frame, decodes it (T2/T3), runs the
   configured `Strategy` (T4/T5), and sends a `RESULT` message back.
4. `TCPEventServer` routes the `RESULT` to `ResultAggregator.record_result()`, which
   computes network/processing/end-to-end latency (T6 = time of receipt) and marks the
   sequence number as received.
5. If a worker's heartbeat times out, `ConnectionManager` marks it OFFLINE and
   `RecoveryManager` reassigns any of its pending (dispatched-but-unresulted) events to
   another online worker.
6. `ExperimentController` waits for completion, gathers `ReplayStats` +
   `ResultAggregator.summary()` + worker/failure info, and returns an `ExperimentResult`
   the backend persists to Postgres.

## Why some folders aren't in the PRD's example tree

The PRD's section 45 tree is illustrative; section 6's component list needed homes for
`metrics_engine/`, `aggregator/`, and `experiment_controller/` that aren't literally in
that tree. They're plain top-level Python packages, kept intentionally small and focused.
