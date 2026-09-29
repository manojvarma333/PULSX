import socket
import threading
import time

from aggregator.result_aggregator import ResultAggregator
from event_server.distributor import EventDistributor
from event_server.protocol import FrameReader, MessageType, encode_json
from event_server.recovery import RecoveryManager
from event_server.server import TCPEventServer
from replay.models import MarketEvent
from workers.python.worker import PulseXWorker


def _wait_until(predicate, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _register_raw(sock: socket.socket, worker_id: str) -> None:
    sock.sendall(encode_json(MessageType.REGISTER, {
        "worker_id": worker_id, "hostname": "zombie-host", "language": "python", "version": "1.0",
    }))
    reader = FrameReader()
    while True:
        data = sock.recv(4096)
        for msg_type, payload in reader.feed(data):
            if msg_type == MessageType.REGISTER_ACK:
                return


def test_offline_worker_triggers_reassignment_to_healthy_worker():
    aggregator = ResultAggregator()
    server = TCPEventServer(
        host="127.0.0.1", port=0,
        on_result=aggregator.record_result,
        suspected_timeout=0.1, offline_timeout=0.2,
    )
    server.start()
    distributor = EventDistributor(server, aggregator=aggregator)
    recovery = RecoveryManager(aggregator, distributor)
    server.on_worker_status_change = recovery.on_worker_status_change

    # "Zombie" worker: registers, then never heartbeats/reads/responds again (simulates a hang/crash).
    zombie = socket.create_connection(("127.0.0.1", server.actual_port), timeout=5)
    _register_raw(zombie, "zombie")

    worker = PulseXWorker("healthy", "127.0.0.1", server.actual_port, strategy_name="passthrough", heartbeat_interval=0.05)
    worker_thread = threading.Thread(target=worker.run_forever, daemon=True)
    worker_thread.start()

    try:
        assert _wait_until(lambda: len(server.connection_manager.online_worker_ids()) == 2)

        event = MarketEvent(1, 1000, "BTCUSD", 100.0, 1, "B")
        # Zombie registered first -> round-robin cursor picks it for the first publish.
        assert _wait_until(lambda: distributor.publish(event))

        # Zombie never heartbeats again -> goes SUSPECTED -> OFFLINE -> event reassigned -> processed.
        assert _wait_until(lambda: aggregator.summary()["events_received"] == 1, timeout=3.0)

        assert len(recovery.failures) == 1
        assert recovery.failures[0].worker_id == "zombie"
        assert recovery.failures[0].reassigned_events == 1
        assert aggregator.missing_sequences() == []
    finally:
        worker.stop()
        try:
            zombie.close()
        except OSError:
            pass
        server.stop()
