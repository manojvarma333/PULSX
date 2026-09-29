from threading import Thread

from experiment_controller.config import ExperimentConfig
from experiment_controller.controller import ExperimentController
from tools.generate_market_data import generate_records, write_csv
from workers.python.worker import PulseXWorker


def _generate_dataset(tmp_path, events=200):
    timestamps, symbols, prices, quantities, sides = generate_records(
        events=events, symbols=3, price_min=10.0, price_max=100.0,
        qty_min=1, qty_max=10, start_timestamp=0, interval=1, jitter=0, seed=1,
    )
    path = tmp_path / "dataset.csv"
    write_csv(path, timestamps, symbols, prices, quantities, sides, seed=1)
    return path


def test_controller_runs_end_to_end_with_thread_workers(tmp_path):
    dataset = _generate_dataset(tmp_path, events=150)
    config = ExperimentConfig(
        name="ci-smoke-test",
        dataset_file=str(dataset),
        protocol="json",
        worker_language="python",
        worker_count=2,
        strategy="passthrough",
        replay_mode="maximum",
        heartbeat_interval=0.5,
        completion_timeout=10.0,
    )
    controller = ExperimentController(config, worker_launch_mode="thread")
    result = controller.run()

    assert result.replay_stats["events_sent"] == 150
    assert result.aggregator_summary["events_received"] == 150
    assert result.aggregator_summary["missing_events"] == []
    assert len(result.workers) == 2
    assert result.system_info["python_version"]
    assert result.config["strategy"] == "passthrough"


def test_controller_with_moving_average_strategy_and_binary_protocol(tmp_path):
    dataset = _generate_dataset(tmp_path, events=80)
    config = ExperimentConfig(
        name="binary-smoke-test",
        dataset_file=str(dataset),
        protocol="binary",
        worker_count=1,
        strategy="moving_average",
        strategy_kwargs={"window": 10},
        replay_mode="maximum",
        heartbeat_interval=0.5,
        completion_timeout=10.0,
    )
    controller = ExperimentController(config, worker_launch_mode="thread")
    result = controller.run()

    assert result.aggregator_summary["events_received"] == 80
    assert result.aggregator_summary["missing_events"] == []


def test_cpp_worker_without_binary_raises_clear_error(tmp_path):
    import pytest
    dataset = _generate_dataset(tmp_path, events=10)
    config = ExperimentConfig(
        name="cpp-missing-binary",
        dataset_file=str(dataset),
        worker_language="cpp",
        worker_count=1,
        cpp_worker_binary=str(tmp_path / "does_not_exist"),
    )
    controller = ExperimentController(config, worker_launch_mode="process")
    with pytest.raises(RuntimeError, match="not found"):
        controller.run()


def _free_port() -> int:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_external_worker_launch_mode_waits_for_outside_connections(tmp_path):
    dataset = _generate_dataset(tmp_path, events=20)
    port = _free_port()
    config = ExperimentConfig(
        name="external-mode-test", dataset_file=str(dataset), worker_count=1,
        strategy="passthrough", heartbeat_interval=0.3, completion_timeout=10.0,
    )
    controller = ExperimentController(config, host="127.0.0.1", port=port, worker_launch_mode="external")

    result_holder = {}

    def _run():
        result_holder["result"] = controller.run()

    controller_thread = Thread(target=_run, daemon=True)
    controller_thread.start()

    worker = PulseXWorker("external-1", "127.0.0.1", port, strategy_name="passthrough", heartbeat_interval=0.3)
    worker_thread = Thread(target=worker.run_forever, daemon=True)
    worker_thread.start()
    try:
        controller_thread.join(timeout=15)
        assert "result" in result_holder
        result = result_holder["result"]
        assert result.aggregator_summary["events_received"] == 20
        assert result.aggregator_summary["missing_events"] == []
    finally:
        worker.stop()
        worker_thread.join(timeout=3)
