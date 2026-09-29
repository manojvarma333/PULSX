"""TCP Event Server (PRD section 11): accepts worker connections, handles registration,
heartbeats and results, and exposes `send_event`/`broadcast` for the distributor to push
market events to connected workers.
"""
from __future__ import annotations

import logging
import socket
import threading
from collections.abc import Callable

from event_server.connection_manager import ConnectionManager, WorkerStatus
from event_server.protocol import FrameReader, MessageType, decode_json, encode_json

logger = logging.getLogger("pulsex.event_server")

ResultCallback = Callable[[str, dict], None]
StatusChangeCallback = Callable[[str, WorkerStatus], None]


class TCPEventServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        on_result: ResultCallback | None = None,
        on_worker_status_change: StatusChangeCallback | None = None,
        suspected_timeout: float | None = None,
        offline_timeout: float | None = None,
    ):
        self.host = host
        self.port = port
        cm_kwargs = {}
        if suspected_timeout is not None:
            cm_kwargs["suspected_timeout"] = suspected_timeout
        if offline_timeout is not None:
            cm_kwargs["offline_timeout"] = offline_timeout
        self.connection_manager = ConnectionManager(**cm_kwargs)
        self.on_result = on_result
        self.on_worker_status_change = on_worker_status_change
        self._server_socket: socket.socket | None = None
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def actual_port(self) -> int:
        assert self._server_socket is not None
        return self._server_socket.getsockname()[1]

    def start(self) -> None:
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(128)
        self._server_socket.settimeout(1.0)

        accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        heartbeat_thread = threading.Thread(target=self._heartbeat_check_loop, daemon=True)
        accept_thread.start()
        heartbeat_thread.start()
        self._threads = [accept_thread, heartbeat_thread]

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
        for t in self._threads:
            t.join(timeout=timeout)

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                conn, _addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            handler = threading.Thread(target=self._handle_connection, args=(conn,), daemon=True)
            handler.start()

    def _handle_connection(self, conn: socket.socket) -> None:
        conn.settimeout(1.0)
        reader = FrameReader()
        worker_id: str | None = None
        try:
            while not self._stop_event.is_set():
                try:
                    data = conn.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                for msg_type, payload in reader.feed(data):
                    if msg_type == MessageType.REGISTER:
                        worker_id = self._handle_register(conn, payload)
                    elif msg_type == MessageType.HEARTBEAT:
                        self._handle_heartbeat(payload)
                    elif msg_type == MessageType.RESULT:
                        self._handle_result(worker_id, payload)
                    elif msg_type == MessageType.SHUTDOWN:
                        return
        except (ConnectionError, OSError):
            pass
        finally:
            if worker_id is not None:
                self.connection_manager.unregister(worker_id)
            try:
                conn.close()
            except OSError:
                pass

    def _handle_register(self, conn: socket.socket, payload: bytes) -> str:
        d = decode_json(payload)
        worker_id = d["worker_id"]
        self.connection_manager.register(worker_id, d.get("hostname", ""), d.get("language", ""), d.get("version", ""), conn)
        try:
            conn.sendall(encode_json(MessageType.REGISTER_ACK, {"worker_id": worker_id, "status": "ok"}))
        except OSError:
            pass
        return worker_id

    def _handle_heartbeat(self, payload: bytes) -> None:
        d = decode_json(payload)
        self.connection_manager.update_heartbeat(
            worker_id=d["worker_id"],
            cpu_usage=d.get("cpu_usage", 0.0),
            memory_usage=d.get("memory_usage", 0.0),
            events_processed=d.get("events_processed", 0),
            events_failed=d.get("events_failed", 0),
            last_processed_sequence=d.get("last_processed_sequence"),
        )

    def _handle_result(self, worker_id: str | None, payload: bytes) -> None:
        d = decode_json(payload)
        if self.on_result is not None:
            self.on_result(worker_id or d.get("worker_id", "unknown"), d)

    def _heartbeat_check_loop(self) -> None:
        while not self._stop_event.wait(1.0):
            for worker_id, new_status in self.connection_manager.check_timeouts():
                logger.warning("worker %s -> %s", worker_id, new_status)
                if self.on_worker_status_change is not None:
                    self.on_worker_status_change(worker_id, new_status)

    def send_event(self, worker_id: str, frame: bytes) -> bool:
        conn = self.connection_manager.get_connection(worker_id)
        if conn is None:
            return False
        try:
            conn.sendall(frame)
            return True
        except OSError:
            self.connection_manager.unregister(worker_id)
            return False
