# PulseX Message Protocol

Canonical spec -- `event_server/protocol.py` is the reference implementation (Python), and
`workers/cpp/src/protocol.cpp` must stay byte-for-byte compatible with it.

## Framing

Every message on the wire is a 5-byte header followed by its payload:

```
+----------------+----------------------+-----------------+
| msg_type (u8)  | payload_length (u32) | payload (bytes) |
+----------------+----------------------+-----------------+
```

- `msg_type`: see Message Types below.
- `payload_length`: **big-endian** `uint32`, length of `payload` only (header not included).

Because TCP is a byte stream, a `FrameReader` on both ends reassembles complete messages
from arbitrary `recv()` chunks -- one `send()` never has to correspond to one complete
message, and multiple messages may arrive in a single `recv()`.

## Message types

| Value | Name          | Payload encoding | Direction          |
|-------|---------------|-------------------|---------------------|
| 1     | REGISTER      | JSON              | worker -> server     |
| 2     | REGISTER_ACK  | JSON              | server -> worker     |
| 3     | HEARTBEAT     | JSON              | worker -> server     |
| 4     | EVENT_JSON    | JSON (Protocol A) | server -> worker     |
| 5     | EVENT_BINARY  | binary (Protocol B) | server -> worker   |
| 6     | RESULT        | JSON              | worker -> server     |
| 7     | SHUTDOWN      | (empty)           | either               |
| 8     | ERROR         | JSON              | either               |

## Control message payloads (JSON)

```jsonc
// REGISTER
{"worker_id": "py-1", "hostname": "host", "language": "python", "version": "1.0"}

// REGISTER_ACK
{"worker_id": "py-1", "status": "ok"}

// HEARTBEAT
{
  "worker_id": "py-1", "cpu_usage": 12.3, "memory_usage": 4.5,
  "events_processed": 100, "events_failed": 1, "last_processed_sequence": 100
}

// RESULT
{
  "worker_id": "py-1", "sequence_number": 42, "success": true,
  "result": {"symbol": "BTCUSD", "price": 65000.2},
  "error": null,
  "dispatched_at_ns": 1, "received_at_ns": 2, "decoded_at_ns": 3,
  "processing_started_ns": 4, "processing_completed_ns": 5
}
```

## Event payloads

Both `EVENT_JSON` and `EVENT_BINARY` payloads are prefixed with an 8-byte little-endian
`int64` **dispatched_at_ns** (T1 in the latency pipeline, PRD section 17-18) so the
receiver can compute network and end-to-end latency, even though sender and receiver are
different processes:

```
+---------------------------+------------------------+
| dispatched_at_ns (i64 LE)  | event body             |
+---------------------------+------------------------+
```

### Protocol A -- EVENT_JSON body

```json
{"sequence_number": 42, "timestamp": 1710000000001, "symbol": "BTCUSD", "price": 65000.2, "quantity": 10, "side": "B"}
```

### Protocol B -- EVENT_BINARY body (37 bytes, little-endian)

| Offset | Size | Field           | Type                          |
|--------|------|-----------------|-------------------------------|
| 0      | 8    | timestamp       | int64                          |
| 8      | 8    | symbol          | ASCII, NUL-padded, max 8 chars |
| 16     | 8    | price           | float64                        |
| 24     | 4    | quantity        | uint32                          |
| 28     | 1    | side            | uint8 (0 = Buy, 1 = Sell)        |
| 29     | 8    | sequence_number | uint64                            |

Total EVENT_BINARY payload size = 8 (dispatch prefix) + 37 (body) = 45 bytes.

## Why perf_counter_ns() / steady_clock across processes is valid here

All PulseX processes run on the same physical machine (this is explicitly a local
research system, PRD section 19/50). `time.perf_counter_ns()` (Python) and
`std::chrono::steady_clock` (C++) are both ultimately backed by the same OS monotonic
clock (QueryPerformanceCounter on Windows, `clock_gettime(CLOCK_MONOTONIC)` on Linux),
which is a *system-wide*, not per-process, clock. Comparing these timestamps across
processes on the same host is therefore valid; it would NOT be valid across different
machines without clock synchronization, which this project never attempts.
