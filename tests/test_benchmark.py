from benchmark.analyzer import compare, format_table
from benchmark.report import write_report
from benchmark.runner import BenchmarkCase, BenchmarkRunner
from tools.generate_market_data import generate_records, write_csv


def _generate_dataset(tmp_path, events=100):
    timestamps, symbols, prices, quantities, sides = generate_records(
        events=events, symbols=3, price_min=10.0, price_max=100.0,
        qty_min=1, qty_max=10, start_timestamp=0, interval=1, jitter=0, seed=5,
    )
    path = tmp_path / "bench.csv"
    write_csv(path, timestamps, symbols, prices, quantities, sides, seed=5)
    return path


def test_benchmark_matrix_produces_real_measured_results(tmp_path):
    dataset = _generate_dataset(tmp_path, events=60)
    runner = BenchmarkRunner(str(dataset), worker_launch_mode="thread")

    cases = [
        BenchmarkCase(protocol="json", worker_count=1, strategy="passthrough"),
        BenchmarkCase(protocol="binary", worker_count=2, strategy="passthrough"),
    ]
    results = runner.run_matrix(cases)

    assert len(results) == 2
    for result in results:
        assert result.replay_stats["events_sent"] == 60
        assert result.aggregator_summary["events_received"] == 60
        assert result.aggregator_summary["missing_events"] == []

    rows = compare(results)
    assert len(rows) == 2
    assert rows[0]["protocol"] == "json"
    assert rows[1]["protocol"] == "binary"
    assert rows[1]["worker_count"] == 2
    # Every throughput/latency figure must come from the actual run, never a placeholder.
    for row in rows:
        assert row["throughput_events_per_sec"] > 0
        assert row["events"] == 60

    table = format_table(rows)
    assert "protocol" in table
    assert "json" in table and "binary" in table


def test_write_report_generates_json_and_markdown(tmp_path):
    dataset = _generate_dataset(tmp_path, events=30)
    runner = BenchmarkRunner(str(dataset), worker_launch_mode="thread")
    result = runner.run_case(BenchmarkCase(protocol="json", worker_count=1, strategy="statistics"))

    json_path, md_path = write_report(result, str(tmp_path / "reports"))

    assert json_path.exists()
    assert md_path.exists()
    content = md_path.read_text()
    assert "Experiment Summary" in content
    assert str(result.replay_stats["events_sent"]) in content
    assert "Throughput:" in content
