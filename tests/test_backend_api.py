import time

import pytest
from fastapi.testclient import TestClient

from backend.app.database import session as db_session
from tools.generate_market_data import generate_records, write_csv


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    db_session.reset_engine_cache()

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client

    db_session.reset_engine_cache()


def _generate_dataset(tmp_path, events=40):
    timestamps, symbols, prices, quantities, sides = generate_records(
        events=events, symbols=2, price_min=10.0, price_max=50.0, qty_min=1, qty_max=5,
        start_timestamp=0, interval=1, jitter=0, seed=2,
    )
    path = tmp_path / "ds.csv"
    write_csv(path, timestamps, symbols, prices, quantities, sides, seed=2)
    return path


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"] == "ok"


def test_run_experiment_end_to_end_via_api(client, tmp_path):
    dataset = _generate_dataset(tmp_path)
    resp = client.post("/experiments/run", json={
        "name": "api-smoke-test",
        "dataset_file": str(dataset),
        "worker_count": 1,
        "strategy": "passthrough",
        "heartbeat_interval": 0.3,
        "completion_timeout": 10.0,
    })
    assert resp.status_code == 202
    experiment_id = resp.json()["experiment_id"]

    deadline = time.time() + 15
    status = None
    while time.time() < deadline:
        status = client.get(f"/experiments/{experiment_id}/status").json()
        if status["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert status["status"] == "completed", status

    detail = client.get(f"/experiments/{experiment_id}").json()
    assert detail["status"] == "completed"
    assert detail["worker_count"] == 1
    assert len(detail["workers"]) == 1
    assert len(detail["metrics"]) == 1

    listed = client.get("/experiments").json()
    assert any(e["id"] == experiment_id for e in listed)

    workers = client.get(f"/experiments/{experiment_id}/workers").json()
    assert len(workers) == 1

    metrics = client.get(f"/experiments/{experiment_id}/metrics").json()
    assert len(metrics) == 1
    assert metrics[0]["event_count"] == 40


def test_unknown_experiment_status_returns_404(client):
    resp = client.get("/experiments/does-not-exist/status")
    assert resp.status_code == 404


def test_unknown_experiment_detail_returns_404(client):
    resp = client.get("/experiments/does-not-exist")
    assert resp.status_code == 404
