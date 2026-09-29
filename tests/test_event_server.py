import socket
import threading
import time

from event_server.connection_manager import WorkerStatus
from event_server.distributor import EventDistributor
from event_server.protocol import FrameReader, MessageType, decode_event, decode_json, encode_json
from event_server.server import TCPEventServer
from replay.models import MarketEvent


def _start_server(**kwargs) -> TCPEventServer:
    server = TCPEventServer(host="127.0.0.1", port=0, **kwargs)
    server.start()
    return server


def _register(sock: socket.socket, worker_id: str):
    sock.sendall(encode_json(MessageType.REGISTER, {
        "worker_id": worker_id, "hostname": "test-host", "language": "python", "version": "1.0",
    }))
    reader = FrameReader()
    while True:
        data = sock.recv(4096)
        for msg_type, payload in reader.feed(data):
            if msg_type == MessageType.REGISTER_ACK:
                return decode_json(payload)


def test_worker_registration_over_real_tcp():
    server = _start_server()
    try:
        with socket.create_connection(("127.0.0.1", server.actual_port), timeout=5) as sock:
            ack = _register(sock, "worker-1")
            assert ack["status"] == "ok"

            deadline = time.time() + 2
            while time.time() < deadline and server.connection_manager.get("worker-1") is None:
                time.sleep(0.02)

            info = server.connection_manager.get("worker-1")
            assert info is not None
            assert info.status == WorkerStatus.ONLINE
    finally:
        server.stop()


def test_distributor_sends_event_to_registered_worker():
    received = []

    server = _start_server()
    try:
        with socket.create_connection(("127.0.0.1", server.actual_port), timeout=5) as sock:
            _register(sock, "worker-1")

            distributor = EventDistributor(server, binary_protocol=False)
            event = MarketEvent(1, 1710000000001, "BTCUSD", 65000.2, 10, "B")

            deadline = time.time() + 2
            sent = False
            while time.time() < deadline and not sent:
                sent = distributor.publish(event)
                if not sent:
                    time.sleep(0.02)
            assert sent

            sock.settimeout(2)
            data = sock.recv(4096)
            reader = FrameReader()
            msgs = list(reader.feed(data))
            assert msgs[0][0] == MessageType.EVENT_JSON
            decoded_event, dispatched_at_ns = decode_event(msgs[0][0], msgs[0][1])
            received.append(decoded_event)

        assert received[0].symbol == "BTCUSD"
    finally:
        server.stop()


def test_distributor_reports_drop_when_no_workers_online():
    server = _start_server()
    try:
        distributor = EventDistributor(server)
        event = MarketEvent(1, 1, "BTCUSD", 100.0, 1, "B")
        assert distributor.publish(event) is False
    finally:
        server.stop()


def test_heartbeat_updates_worker_metrics():
    server = _start_server()
    try:
        with socket.create_connection(("127.0.0.1", server.actual_port), timeout=5) as sock:
            _register(sock, "worker-1")
            sock.sendall(encode_json(MessageType.HEARTBEAT, {
                "worker_id": "worker-1", "cpu_usage": 42.0, "memory_usage": 12.5,
                "events_processed": 10, "events_failed": 1, "last_processed_sequence": 10,
            }))

            deadline = time.time() + 2
            info = None
            while time.time() < deadline:
                info = server.connection_manager.get("worker-1")
                if info and info.cpu_usage == 42.0:
                    break
                time.sleep(0.02)

            assert info.cpu_usage == 42.0
            assert info.events_processed == 10
    finally:
        server.stop()
