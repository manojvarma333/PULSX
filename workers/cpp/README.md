# PulseX C++ Worker

C++17 counterpart to `workers/python/worker.py`. Same wire protocol (`docs/protocol.md`),
same strategy set, same TCP event-server -- used to compare Python vs C++ processing
performance (PRD section 22).

> **Note:** this code was written without a local C++ toolchain available (no `g++` on
> the authoring machine) and has not been compiled/tested locally. Build it via Docker
> (which uses `gcc:13`) or on a Linux/WSL2 machine with a C++17 compiler + CMake >= 3.16
> before relying on it, and report any build errors so they can be fixed.

## Build

Via Docker (recommended, no local toolchain needed):
```
docker build -t pulsex-cpp-worker workers/cpp
```

Locally on Linux/WSL2 with g++ and CMake installed:
```
cmake -S workers/cpp -B workers/cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build workers/cpp/build -j
ctest --test-dir workers/cpp/build --output-on-failure
```

## Run

```
./workers/cpp/build/pulsex_cpp_worker --worker-id cpp-1 --host 127.0.0.1 --port 9000 \
    --strategy moving_average --heartbeat-interval 5.0
```

Or via Docker:
```
docker run --rm --network host pulsex-cpp-worker --worker-id cpp-1 --host 127.0.0.1 --port 9000
```

## Design notes

- Linux/WSL2 only (uses POSIX sockets and `/proc` for CPU/memory sampling) -- matches the
  project's primary deployment target.
- Uses `nlohmann/json` (fetched via CMake `FetchContent`) for all JSON control messages,
  and a hand-written little-endian packer for the binary event format to match
  `event_server/protocol.py` exactly.
- `std::chrono::steady_clock` is used for all latency timestamps, matching
  `time.perf_counter_ns()` on the Python side -- both are backed by `CLOCK_MONOTONIC` on
  Linux, so cross-process comparison between a Python and C++ worker on the same host is
  valid (this system never compares timestamps across different machines).
