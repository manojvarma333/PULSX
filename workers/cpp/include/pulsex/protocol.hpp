#pragma once
// Wire protocol shared with event_server/protocol.py -- MUST stay byte-for-byte
// compatible. See docs/protocol.md for the canonical spec.
#include <cstdint>
#include <functional>
#include <string>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>

namespace pulsex {

enum class MessageType : uint8_t {
    Register = 1,
    RegisterAck = 2,
    Heartbeat = 3,
    EventJson = 4,
    EventBinary = 5,
    Result = 6,
    Shutdown = 7,
    Error = 8,
};

constexpr size_t kHeaderSize = 5;         // 1 byte msg_type + 4 byte big-endian length
constexpr size_t kDispatchPrefixSize = 8;  // int64 little-endian dispatched_at_ns (T1)
constexpr size_t kBinaryEventBodySize = 37;  // timestamp(8)+symbol(8)+price(8)+qty(4)+side(1)+seq(8)

struct MarketEvent {
    int64_t sequence_number = 0;
    int64_t timestamp = 0;
    std::string symbol;
    double price = 0.0;
    uint32_t quantity = 0;
    char side = 'B';  // 'B' or 'S'

    bool operator==(const MarketEvent& other) const {
        return sequence_number == other.sequence_number && timestamp == other.timestamp &&
               symbol == other.symbol && price == other.price && quantity == other.quantity &&
               side == other.side;
    }
};

std::vector<uint8_t> encode_frame(MessageType type, const std::vector<uint8_t>& payload);
std::vector<uint8_t> encode_json(MessageType type, const nlohmann::json& obj);
nlohmann::json decode_json(const std::vector<uint8_t>& payload);

std::vector<uint8_t> encode_event_binary(const MarketEvent& event);
MarketEvent decode_event_binary(const std::vector<uint8_t>& payload);

// Returns (event, dispatched_at_ns) -- the T1 timestamp recorded when the event was sent.
std::pair<MarketEvent, int64_t> decode_event(MessageType type, const std::vector<uint8_t>& payload);

// Incrementally reassembles complete frames from a stream of raw socket bytes -- one
// recv() never has to correspond to one complete message.
class FrameReader {
public:
    using FrameHandler = std::function<void(MessageType, std::vector<uint8_t>)>;
    void feed(const uint8_t* data, size_t len, const FrameHandler& on_frame);

private:
    std::vector<uint8_t> buffer_;
};

int64_t now_ns();

}  // namespace pulsex
