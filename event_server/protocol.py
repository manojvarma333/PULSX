"""Message protocol and framing for PulseX (PRD section 11-12).

Wire format (all messages): a fixed 5-byte header followed by the payload.

    +----------------+----------------------+-----------------+
    | msg_type (u8)  | payload_length (u32) | payload (bytes) |
    +----------------+----------------------+-----------------+

`payload_length` is big-endian and does not include the 5-byte header itself. This lets a
`FrameReader` reassemble complete messages from an arbitrary stream of `recv()` chunks --
one `send()` never has to correspond to one complete message.

Control messages (REGISTER, HEARTBEAT, RESULT, ...) are always JSON. Market events can be
serialized as either JSON (Protocol A) or a compact fixed-size binary layout (Protocol B),
selected per-experiment via configuration.

Binary event layout (37 bytes, little-endian), documented per PRD section 12:

    offset  size  field
    0       8     timestamp   (int64)
    8       8     symbol      (ASCII, NUL-padded, max 8 chars)
    16      8     price       (float64)
    24      4     quantity    (uint32)
    28      1     side        (uint8: 0=Buy, 1=Sell)
    29      8     sequence_number (uint64)

EVENT_JSON/EVENT_BINARY payloads are additionally prefixed with an 8-byte int64
"dispatched_at_ns" (perf_counter_ns() at send time, T1) so the receiver can compute
network/end-to-end latency (PRD section 18). All PulseX processes run on the same
machine, where perf_counter_ns() is a shared system-wide monotonic clock (QPC on
Windows, CLOCK_MONOTONIC on Linux), so cross-process comparison is valid here.
"""
from __future__ import annotations

import json
import struct
import time
from collections.abc import Iterator
from enum import IntEnum

from replay.models import MarketEvent

HEADER_STRUCT = struct.Struct(">BI")  # msg_type, payload_length
HEADER_SIZE = HEADER_STRUCT.size

_DISPATCH_TS_STRUCT = struct.Struct("<q")  # dispatched_at_ns
_BINARY_EVENT_STRUCT = struct.Struct("<q8sdIBQ")  # timestamp, symbol, price, quantity, side, sequence_number
BINARY_EVENT_SIZE = _BINARY_EVENT_STRUCT.size

_SIDE_TO_BYTE = {"B": 0, "S": 1}
_BYTE_TO_SIDE = {0: "B", 1: "S"}


class MessageType(IntEnum):
    REGISTER = 1
    REGISTER_ACK = 2
    HEARTBEAT = 3
    EVENT_JSON = 4
    EVENT_BINARY = 5
    RESULT = 6
    SHUTDOWN = 7
    ERROR = 8


class ProtocolError(Exception):
    pass


def encode_frame(msg_type: MessageType, payload: bytes) -> bytes:
    return HEADER_STRUCT.pack(int(msg_type), len(payload)) + payload


def encode_json(msg_type: MessageType, obj: dict) -> bytes:
    return encode_frame(msg_type, json.dumps(obj).encode("utf-8"))


def decode_json(payload: bytes) -> dict:
    return json.loads(payload.decode("utf-8"))


def encode_event(event: MarketEvent, binary: bool, dispatched_at_ns: int | None = None) -> bytes:
    if dispatched_at_ns is None:
        dispatched_at_ns = time.perf_counter_ns()
    ts_prefix = _DISPATCH_TS_STRUCT.pack(dispatched_at_ns)
    if binary:
        return encode_frame(MessageType.EVENT_BINARY, ts_prefix + encode_event_binary(event))
    body = json.dumps(
        {
            "sequence_number": event.sequence_number,
            "timestamp": event.timestamp,
            "symbol": event.symbol,
            "price": event.price,
            "quantity": event.quantity,
            "side": event.side,
        }
    ).encode("utf-8")
    return encode_frame(MessageType.EVENT_JSON, ts_prefix + body)


def decode_event(msg_type: MessageType, payload: bytes) -> tuple[MarketEvent, int]:
    """Returns (event, dispatched_at_ns) -- the T1 timestamp recorded when the event was sent."""
    (dispatched_at_ns,) = _DISPATCH_TS_STRUCT.unpack_from(payload, 0)
    body = payload[_DISPATCH_TS_STRUCT.size:]
    if msg_type == MessageType.EVENT_BINARY:
        return decode_event_binary(body), dispatched_at_ns
    if msg_type == MessageType.EVENT_JSON:
        d = decode_json(body)
        event = MarketEvent(
            sequence_number=d["sequence_number"],
            timestamp=d["timestamp"],
            symbol=d["symbol"],
            price=d["price"],
            quantity=d["quantity"],
            side=d["side"],
        )
        return event, dispatched_at_ns
    raise ProtocolError(f"not an event message type: {msg_type!r}")


def encode_event_binary(event: MarketEvent) -> bytes:
    symbol_bytes = event.symbol.encode("ascii")[:8].ljust(8, b"\x00")
    try:
        side_byte = _SIDE_TO_BYTE[event.side]
    except KeyError as exc:
        raise ProtocolError(f"invalid side: {event.side!r}") from exc
    return _BINARY_EVENT_STRUCT.pack(
        event.timestamp, symbol_bytes, event.price, event.quantity, side_byte, event.sequence_number
    )


def decode_event_binary(payload: bytes) -> MarketEvent:
    if len(payload) != BINARY_EVENT_SIZE:
        raise ProtocolError(f"binary event payload must be {BINARY_EVENT_SIZE} bytes, got {len(payload)}")
    timestamp, symbol_bytes, price, quantity, side_byte, sequence_number = _BINARY_EVENT_STRUCT.unpack(payload)
    symbol = symbol_bytes.rstrip(b"\x00").decode("ascii")
    try:
        side = _BYTE_TO_SIDE[side_byte]
    except KeyError as exc:
        raise ProtocolError(f"invalid side byte: {side_byte!r}") from exc
    return MarketEvent(
        sequence_number=sequence_number, timestamp=timestamp, symbol=symbol, price=price, quantity=quantity, side=side
    )


class FrameReader:
    """Incrementally reassembles complete frames from a stream of raw socket bytes."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> Iterator[tuple[MessageType, bytes]]:
        self._buffer.extend(data)
        while True:
            if len(self._buffer) < HEADER_SIZE:
                return
            msg_type_int, payload_length = HEADER_STRUCT.unpack_from(self._buffer, 0)
            total_size = HEADER_SIZE + payload_length
            if len(self._buffer) < total_size:
                return
            payload = bytes(self._buffer[HEADER_SIZE:total_size])
            del self._buffer[:total_size]
            try:
                msg_type = MessageType(msg_type_int)
            except ValueError as exc:
                raise ProtocolError(f"unknown message type: {msg_type_int}") from exc
            yield msg_type, payload
