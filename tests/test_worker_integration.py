import threading
import time

from event_server.distributor import EventDistributor
from event_server.server import TCPEventServer
from replay.models import MarketEvent
from workers.python.worker import PulseXWorker


def _wait_until(predicate, timeout=3.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _publish_all(distributor, events, timeout=3.0):
    for event in events:
        assert _wait_until(lambda: distributor.publish(event), timeout=timeout)


def test_single_worker_processes_events_end_to_end():
    results = []
    server = TCPEventServer(host="127.0.0.1", port=0, on_result=lambda wid, payload: results.append(payload))
    server.start()
    worker = PulseXWorker("py-1", "127.0.0.1", server.actual_port, strategy_name="moving_average", heartbeat_interval=1.0)
    worker_thread = threading.Thread(target=worker.run_forever, daemon=True)
    worker_thread.start()
    try:
        assert _wait_until(lambda: server.connection_manager.get("py-1") is not None)

        distributor = EventDistributor(server, binary_protocol=False)
        events = [MarketEvent(i, i * 1000, "BTCUSD", 100.0 + i, 10, "B") for i in range(1, 11)]
        _publish_all(distributor, events)

        assert _wait_until(lambda: len(results) == 10)
        assert all(r["success"] for r in results)
        assert {r["sequence_number"] for r in results} == set(range(1, 11))
        # T1 <= T2 <= T4 <= T5 for every result (monotonic pipeline stages).
        for r in results:
            assert r["dispatched_at_ns"] <= r["received_at_ns"] <= r["processing_started_ns"] <= r["processing_completed_ns"]
    finally:
        worker.stop()
        server.stop()


def test_binary_protocol_end_to_end():
    results = []
    server = TCPEventServer(host="127.0.0.1", port=0, on_result=lambda wid, payload: results.append(payload))
    server.start()
    worker = PulseXWorker("py-bin", "127.0.0.1", server.actual_port, strategy_name="passthrough", heartbeat_interval=1.0)
    worker_thread = threading.Thread(target=worker.run_forever, daemon=True)
    worker_thread.start()
    try:
        assert _wait_until(lambda: server.connection_manager.get("py-bin") is not None)
        distributor = EventDistributor(server, binary_protocol=True)
        events = [MarketEvent(i, i * 1000, "ETHUSD", 10.0 + i, 1, "S") for i in range(1, 6)]
        _publish_all(distributor, events)

        assert _wait_until(lambda: len(results) == 5)
        assert all(r["result"]["symbol"] == "ETHUSD" for r in results)
    finally:
        worker.stop()
        server.stop()


def test_failure_strategy_reports_unsuccessful_results():
    results = []
    server = TCPEventServer(host="127.0.0.1", port=0, on_result=lambda wid, payload: results.append(payload))
    server.start()
    worker = PulseXWorker(
        "py-fail", "127.0.0.1", server.actual_port,
        strategy_name="failure", strategy_kwargs={"failure_probability": 1.0, "seed": 1},
        heartbeat_interval=1.0,
    )
    worker_thread = threading.Thread(target=worker.run_forever, daemon=True)
    worker_thread.start()
    try:
        assert _wait_until(lambda: server.connection_manager.get("py-fail") is not None)
        distributor = EventDistributor(server)
        _publish_all(distributor, [MarketEvent(1, 1000, "BTCUSD", 100.0, 1, "B")])

        assert _wait_until(lambda: len(results) == 1)
        assert results[0]["success"] is False
        assert results[0]["error"] is not None
    finally:
        worker.stop()
        server.stop()


def test_multiple_workers_share_the_load_round_robin():
    results = []
    lock = threading.Lock()

    def on_result(worker_id, payload):
        with lock:
            results.append((worker_id, payload))

    server = TCPEventServer(host="127.0.0.1", port=0, on_result=on_result)
    server.start()
    workers = [
        PulseXWorker(f"py-{i}", "127.0.0.1", server.actual_port, strategy_name="passthrough", heartbeat_interval=1.0)
        for i in range(3)
    ]
    threads = [threading.Thread(target=w.run_forever, daemon=True) for w in workers]
    for t in threads:
        t.start()
    try:
        assert _wait_until(lambda: len(server.connection_manager.online_worker_ids()) == 3)

        distributor = EventDistributor(server)
        events = [MarketEvent(i, i * 1000, "BTCUSD", 100.0, 1, "B") for i in range(1, 31)]
        _publish_all(distributor, events)

        assert _wait_until(lambda: len(results) == 30)
        by_worker = {}
        for worker_id, _ in results:
            by_worker[worker_id] = by_worker.get(worker_id, 0) + 1
        assert len(by_worker) == 3
        assert all(count == 10 for count in by_worker.values())  # even round-robin split
    finally:
        for w in workers:
            w.stop()
        server.stop()
