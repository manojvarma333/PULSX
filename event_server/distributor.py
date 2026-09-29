"""Event Distributor (PRD component #5): picks a worker for each event and sends it.

Round-robins across currently ONLINE workers. If no worker is online, the event is
reported as dropped so the caller (replay engine) can account for it. When an
`aggregator` is supplied, every successful dispatch is recorded so the ResultAggregator
can detect missing sequence numbers and the RecoveryManager can reassign in-flight work.
"""
from __future__ import annotations

from event_server.protocol import encode_event
from event_server.server import TCPEventServer
from replay.models import MarketEvent


class EventDistributor:
    def __init__(self, server: TCPEventServer, binary_protocol: bool = False, aggregator=None):
        self._server = server
        self._binary_protocol = binary_protocol
        self._aggregator = aggregator
        self._cursor = 0

    def _next_worker_id(self) -> str | None:
        online = self._server.connection_manager.online_worker_ids()
        if not online:
            return None
        cursor = self._cursor % len(online)
        self._cursor = cursor + 1
        return online[cursor]

    def publish(self, event: MarketEvent) -> bool:
        """Publish one event to the next worker in round-robin order. Returns True if sent."""
        worker_id = self._next_worker_id()
        if worker_id is None:
            return False
        frame = encode_event(event, binary=self._binary_protocol)
        sent = self._server.send_event(worker_id, frame)
        if sent and self._aggregator is not None:
            self._aggregator.record_dispatch(worker_id, event)
        return sent
