#!/usr/bin/env python3
"""Python worker (PRD section 15): connects to the TCP event server, processes events with
a configurable simulation strategy, and reports heartbeats + per-event results.

Run standalone:
    python -m workers.python.worker --worker-id py-1 --host 127.0.0.1 --port 9000 \
        --strategy moving_average
"""
from __future__ import annotations

import argparse
import logging
import signal
import socket
import sys
import threading
import time

from event_server.protocol import FrameReader, MessageType, decode_event, encode_json
from strategies import create_strategy
from workers.python.metrics import WorkerMetrics

logger = logging.getLogger("pulsex.worker")

RECONNECT_BACKOFFS_SECONDS = (1, 2, 4, 8, 16, 30)


class PulseXWorker:
    def __init__(
        self,
        worker_id: str,
        host: str,
        port: int,
        strategy_name: str = "passthrough",
        strategy_kwargs: dict | None = None,
        heartbeat_interval: float = 5.0,
        version: str = "1.0",
    ):
        self.worker_id = worker_id
        self.host = host
        self.port = port
        self.strategy = create_strategy(strategy_name, **(strategy_kwargs or {}))
        self.heartbeat_interval = heartbeat_interval
        self.version = version
        self.metrics = WorkerMetrics()

        self._stop_event = threading.Event()
        self._send_lock = threading.Lock()
        self._sock: socket.socket | None = None

    def stop(self) -> None:
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def run_forever(self) -> None:
        """Connects and serves events, reconnecting with backoff until stop() is called."""
        attempt = 0
        while not self._stop_event.is_set():
            try:
                self._connect_and_serve()
                attempt = 0
            except (ConnectionError, OSError) as exc:
                logger.warning("worker %s: connection lost (%s)", self.worker_id, exc)
            if self._stop_event.is_set():
                return
            delay = RECONNECT_BACKOFFS_SECONDS[min(attempt, len(RECONNECT_BACKOFFS_SECONDS) - 1)]
            attempt += 1
            logger.info("worker %s: reconnecting in %ss", self.worker_id, delay)
            if self._stop_event.wait(delay):
                return

    def _connect_and_serve(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=5)
        sock.settimeout(1.0)
        self._sock = sock
        try:
            reader = self._register(sock)
            heartbeat_thread = threading.Thread(target=self._heartbeat_loop, args=(sock,), daemon=True)
            heartbeat_thread.start()
            self._receive_loop(sock, reader)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _register(self, sock: socket.socket) -> FrameReader:
        sock.sendall(
            encode_json(
                MessageType.REGISTER,
                {
                    "worker_id": self.worker_id,
                    "hostname": socket.gethostname(),
                    "language": "python",
                    "version": self.version,
                },
            )
        )
        reader = FrameReader()
        while True:
            data = sock.recv(4096)
            if not data:
                raise ConnectionError("server closed connection during registration")
            for msg_type, payload in reader.feed(data):
                if msg_type == MessageType.REGISTER_ACK:
                    return reader

    def _heartbeat_loop(self, sock: socket.socket) -> None:
        while not self._stop_event.is_set():
            snapshot = self.metrics.snapshot()
            snapshot["worker_id"] = self.worker_id
            try:
                with self._send_lock:
                    sock.sendall(encode_json(MessageType.HEARTBEAT, snapshot))
            except OSError:
                return
            if self._stop_event.wait(self.heartbeat_interval):
                return

    def _receive_loop(self, sock: socket.socket, reader: FrameReader) -> None:
        while not self._stop_event.is_set():
            try:
                data = sock.recv(65536)
            except socket.timeout:
                continue
            if not data:
                raise ConnectionError("server closed connection")
            for msg_type, payload in reader.feed(data):
                if msg_type in (MessageType.EVENT_JSON, MessageType.EVENT_BINARY):
                    received_at_ns = time.perf_counter_ns()
                    self._handle_event(sock, msg_type, payload, received_at_ns)

    def _handle_event(self, sock: socket.socket, msg_type: MessageType, payload: bytes, received_at_ns: int) -> None:
        event, dispatched_at_ns = decode_event(msg_type, payload)
        decoded_at_ns = time.perf_counter_ns()

        processing_started_ns = time.perf_counter_ns()
        try:
            result = self.strategy.process(event)
            success, error = True, None
        except Exception as exc:  # simulation strategies may intentionally raise (Strategy 5)
            success, result, error = False, None, str(exc)
        processing_completed_ns = time.perf_counter_ns()

        if success:
            self.metrics.record_success(event.sequence_number)
        else:
            self.metrics.record_failure(event.sequence_number)

        message = {
            "worker_id": self.worker_id,
            "sequence_number": event.sequence_number,
            "success": success,
            "result": result,
            "error": error,
            "dispatched_at_ns": dispatched_at_ns,      # T1
            "received_at_ns": received_at_ns,          # T2
            "decoded_at_ns": decoded_at_ns,             # T3
            "processing_started_ns": processing_started_ns,   # T4
            "processing_completed_ns": processing_completed_ns,  # T5
        }
        try:
            with self._send_lock:
                sock.sendall(encode_json(MessageType.RESULT, message))
        except OSError:
            logger.warning("worker %s: failed to send result for sequence %s", self.worker_id, event.sequence_number)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PulseX Python worker")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--strategy", default="passthrough", choices=[
        "passthrough", "moving_average", "statistics", "cpu_stress", "failure",
    ])
    parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    worker = PulseXWorker(
        worker_id=args.worker_id,
        host=args.host,
        port=args.port,
        strategy_name=args.strategy,
        heartbeat_interval=args.heartbeat_interval,
    )

    def _handle_signal(signum, frame):
        logger.info("worker %s: received signal %s, shutting down", worker.worker_id, signum)
        worker.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
