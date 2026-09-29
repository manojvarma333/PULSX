import time

from aggregator.result_aggregator import ResultAggregator
from event_server.connection_manager import WorkerStatus
from event_server.recovery import RecoveryManager
from replay.models import MarketEvent


def _event(seq):
    return MarketEvent(seq, seq * 1000, "BTCUSD", 100.0, 1, "B")


def test_missing_sequences_detected_when_result_never_arrives():
    agg = ResultAggregator()
    agg.record_dispatch("w1", _event(1))
    agg.record_dispatch("w1", _event(2))
    agg.record_dispatch("w1", _event(3))
    agg.record_result("w1", {"sequence_number": 1, "success": True, "dispatched_at_ns": 0, "received_at_ns": 10})
    agg.record_result("w1", {"sequence_number": 3, "success": True, "dispatched_at_ns": 0, "received_at_ns": 10})

    assert agg.missing_sequences() == [2]


def test_summary_reports_per_worker_and_latency():
    agg = ResultAggregator()
    agg.record_dispatch("w1", _event(1))
    agg.record_result("w1", {
        "sequence_number": 1, "success": True,
        "dispatched_at_ns": 0, "received_at_ns": 1_000_000,
        "processing_started_ns": 1_000_000, "processing_completed_ns": 2_000_000,
    })
    agg.record_dispatch("w1", _event(2))
    agg.record_result("w1", {"sequence_number": 2, "success": False, "dispatched_at_ns": 0, "received_at_ns": 500_000})

    summary = agg.summary()
    assert summary["events_dispatched"] == 2
    assert summary["events_received"] == 2
    assert summary["workers"]["w1"]["events_processed"] == 1
    assert summary["workers"]["w1"]["events_failed"] == 1
    assert summary["network_latency_ms"]["count"] == 2
    assert summary["processing_latency_ms"]["count"] == 1


def test_pending_for_worker_excludes_received_events():
    agg = ResultAggregator()
    agg.record_dispatch("w1", _event(1))
    agg.record_dispatch("w1", _event(2))
    agg.record_result("w1", {"sequence_number": 1, "success": True, "dispatched_at_ns": 0, "received_at_ns": 1})

    pending = agg.pending_for_worker("w1")
    assert [seq for seq, _event in pending] == [2]


class _FakeDistributor:
    def __init__(self):
        self.published = []

    def publish(self, event) -> bool:
        self.published.append(event)
        return True


def test_recovery_manager_reassigns_pending_events_on_offline():
    agg = ResultAggregator()
    agg.record_dispatch("w1", _event(1))
    agg.record_dispatch("w1", _event(2))

    distributor = _FakeDistributor()
    recovery = RecoveryManager(agg, distributor)
    recovery.on_worker_status_change("w1", WorkerStatus.OFFLINE)

    assert len(distributor.published) == 2
    assert agg.pending_for_worker("w1") == []
    assert len(recovery.failures) == 1
    assert recovery.failures[0].reassigned_events == 2


def test_recovery_manager_ignores_non_offline_transitions():
    agg = ResultAggregator()
    distributor = _FakeDistributor()
    recovery = RecoveryManager(agg, distributor)
    recovery.on_worker_status_change("w1", WorkerStatus.SUSPECTED)
    assert recovery.failures == []
