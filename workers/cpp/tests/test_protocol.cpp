// Lightweight assert-based smoke tests (no external test framework, to keep the build
// simple to fetch/compile in Docker). Run via `ctest` or directly executing the binary.
#include <cassert>
#include <iostream>

#include "pulsex/protocol.hpp"
#include "pulsex/strategies.hpp"

using namespace pulsex;

static void test_binary_event_roundtrip() {
    MarketEvent event{42, 1710000000001, "BTCUSD", 65000.20, 10, 'B'};
    auto encoded = encode_event_binary(event);
    assert(encoded.size() == kBinaryEventBodySize);
    auto decoded = decode_event_binary(encoded);
    assert(decoded == event);
    std::cout << "test_binary_event_roundtrip OK\n";
}

static void test_frame_reader_handles_partial_messages() {
    nlohmann::json obj = {{"worker_id", "w1"}};
    auto frame = encode_json(MessageType::Heartbeat, obj);

    FrameReader reader;
    int received = 0;
    for (size_t i = 0; i < frame.size(); ++i) {
        reader.feed(frame.data() + i, 1, [&](MessageType type, std::vector<uint8_t> payload) {
            assert(type == MessageType::Heartbeat);
            auto decoded = decode_json(payload);
            assert(decoded["worker_id"] == "w1");
            received += 1;
        });
    }
    assert(received == 1);
    std::cout << "test_frame_reader_handles_partial_messages OK\n";
}

static void test_decode_event_with_dispatch_prefix() {
    MarketEvent event{1, 1000, "ETHUSD", 10.5, 3, 'S'};
    std::vector<uint8_t> ts_prefix(8, 0);
    ts_prefix[0] = 123;  // dispatched_at_ns = 123 (little-endian)
    auto body = encode_event_binary(event);
    std::vector<uint8_t> payload = ts_prefix;
    payload.insert(payload.end(), body.begin(), body.end());

    auto [decoded, dispatched_at_ns] = decode_event(MessageType::EventBinary, payload);
    assert(decoded == event);
    assert(dispatched_at_ns == 123);
    std::cout << "test_decode_event_with_dispatch_prefix OK\n";
}

static void test_moving_average_strategy() {
    MovingAverageStrategy strat(2);
    strat.process(MarketEvent{1, 1, "BTCUSD", 10.0, 1, 'B'});
    strat.process(MarketEvent{2, 2, "BTCUSD", 20.0, 1, 'B'});
    auto result = strat.process(MarketEvent{3, 3, "BTCUSD", 30.0, 1, 'B'});
    assert(result["moving_average"] == 25.0);
    std::cout << "test_moving_average_strategy OK\n";
}

static void test_failure_strategy_deterministic() {
    FailureSimulationStrategy strat(1.0, 1);
    bool threw = false;
    try {
        strat.process(MarketEvent{1, 1, "BTCUSD", 10.0, 1, 'B'});
    } catch (const std::exception&) {
        threw = true;
    }
    assert(threw);
    std::cout << "test_failure_strategy_deterministic OK\n";
}

int main() {
    test_binary_event_roundtrip();
    test_frame_reader_handles_partial_messages();
    test_decode_event_with_dispatch_prefix();
    test_moving_average_strategy();
    test_failure_strategy_deterministic();
    std::cout << "All C++ protocol/strategy tests passed.\n";
    return 0;
}
