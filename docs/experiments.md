# Running Experiments

## Reproducibility (PRD section 29)

Every `ExperimentResult` (`experiment_controller/controller.py`) carries everything
needed to reproduce it:

- `experiment_id` (UUID, generated per run)
- `config` (the full `ExperimentConfig`, including any `random_seed` you set on the dataset generator)
- `system_info` (OS, CPU model/cores, RAM, Python version, g++/docker versions if
  available, git commit -- `experiment_controller/system_info.py`)
- `started_at` / `finished_at` (UTC ISO-8601 timestamps)

## Running one experiment (Python API)

```python
from experiment_controller.config import ExperimentConfig
from experiment_controller.controller import ExperimentController

config = ExperimentConfig(
    name="demo-1",
    dataset_file="data/generated/market_data_100000.csv",
    protocol="binary",
    worker_language="python",
    worker_count=4,
    strategy="moving_average",
    replay_mode="accelerated",
    speed_multiplier=50,
)
result = ExperimentController(config, worker_launch_mode="process").run()
print(result.aggregator_summary)
```

## Running via the backend API

```
uvicorn backend.app.main:app --reload
```

```bash
curl -X POST localhost:8000/experiments/run -H "Content-Type: application/json" -d '{
  "name": "demo-1",
  "dataset_file": "data/generated/market_data_100000.csv",
  "protocol": "binary",
  "worker_count": 4,
  "strategy": "moving_average"
}'
# -> {"experiment_id": "...", "status": "running"}

curl localhost:8000/experiments/<experiment_id>/status
curl localhost:8000/experiments/<experiment_id>
```

## Worker launch modes

- `worker_launch_mode="thread"`: workers run as in-process Python threads. Fast, used by
  the test suite and small local demos. Not real process isolation.
- `worker_launch_mode="process"`: each worker is a real OS subprocess
  (`python -m workers.python.worker ...`, or the C++ binary). Use this for genuine
  benchmark comparisons and failure/chaos testing (PRD section 47).
- `worker_launch_mode="external"`: the controller spawns nothing and just waits for
  `worker_count` workers to connect on their own -- used for the `cpp-worker` Docker
  Compose service, which connects to an already-running experiment's TCP port from its
  own container (see `docker-compose.yml`).

## Failure/chaos testing

To reproduce PRD section 47's chaos scenarios with `worker_launch_mode="process"`:
- **Kill worker**: `docker kill <container>` or `kill -9 <pid>` (hard crash, no graceful
  shutdown -- tests `RecoveryManager` reassignment).
- **Disconnect worker**: block the worker's TCP connection (e.g. a firewall rule) without
  killing the process -- heartbeats stop, same OFFLINE/reassignment path.
- Every reassignment is recorded in `RecoveryManager.failures` and, once persisted,
  queryable via `GET /experiments/{id}/failures`.
