from event_server.protocol import (
    BINARY_EVENT_SIZE,
    FrameReader,
    MessageType,
    decode_event,
    decode_event_binary,
    decode_json,
    encode_event,
    encode_event_binary,
    encode_json,
)
from replay.models import MarketEvent


def _event(seq=1):
    return MarketEvent(sequence_number=seq, timestamp=1710000000001, symbol="BTCUSD", price=65000.20, quantity=10, side="B")


def test_binary_event_roundtrip():
    event = _event()
    encoded = encode_event_binary(event)
    assert len(encoded) == BINARY_EVENT_SIZE
    decoded = decode_event_binary(encoded)
    assert decoded == event


def test_json_event_roundtrip():
    event = _event(seq=42)
    frame = encode_event(event, binary=False, dispatched_at_ns=123)
    reader = FrameReader()
    msgs = list(reader.feed(frame))
    assert len(msgs) == 1
    msg_type, payload = msgs[0]
    assert msg_type == MessageType.EVENT_JSON
    decoded, dispatched_at_ns = decode_event(msg_type, payload)
    assert decoded == event
    assert dispatched_at_ns == 123


def test_binary_event_frame_roundtrip():
    event = _event(seq=7)
    frame = encode_event(event, binary=True, dispatched_at_ns=456)
    reader = FrameReader()
    (msg_type, payload), = list(reader.feed(frame))
    assert msg_type == MessageType.EVENT_BINARY
    decoded, dispatched_at_ns = decode_event(msg_type, payload)
    assert decoded == event
    assert dispatched_at_ns == 456


def test_frame_reader_handles_partial_and_multiple_messages():
    frame1 = encode_json(MessageType.HEARTBEAT, {"worker_id": "w1"})
    frame2 = encode_json(MessageType.HEARTBEAT, {"worker_id": "w2"})
    combined = frame1 + frame2

    reader = FrameReader()
    # Feed byte-by-byte to prove partial reads are handled.
    received = []
    for i in range(len(combined)):
        received.extend(reader.feed(combined[i:i + 1]))

    assert len(received) == 2
    assert decode_json(received[0][1])["worker_id"] == "w1"
    assert decode_json(received[1][1])["worker_id"] == "w2"


def test_symbol_longer_than_8_chars_is_truncated():
    event = MarketEvent(1, 1, "VERYLONGSYMBOL", 1.0, 1, "B")
    decoded = decode_event_binary(encode_event_binary(event))
    assert decoded.symbol == "VERYLONG"
