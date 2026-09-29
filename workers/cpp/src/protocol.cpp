#include "pulsex/protocol.hpp"

#include <chrono>
#include <cstring>
#include <stdexcept>

namespace pulsex {
namespace {

void put_le(std::vector<uint8_t>& out, uint64_t value, size_t nbytes) {
    for (size_t i = 0; i < nbytes; ++i) {
        out.push_back(static_cast<uint8_t>((value >> (8 * i)) & 0xFF));
    }
}

uint64_t get_le(const uint8_t* data, size_t nbytes) {
    uint64_t value = 0;
    for (size_t i = 0; i < nbytes; ++i) {
        value |= (static_cast<uint64_t>(data[i]) << (8 * i));
    }
    return value;
}

void put_double_le(std::vector<uint8_t>& out, double value) {
    uint64_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    put_le(out, bits, 8);
}

double get_double_le(const uint8_t* data) {
    uint64_t bits = get_le(data, 8);
    double value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

}  // namespace

int64_t now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

std::vector<uint8_t> encode_frame(MessageType type, const std::vector<uint8_t>& payload) {
    std::vector<uint8_t> out;
    out.reserve(kHeaderSize + payload.size());
    out.push_back(static_cast<uint8_t>(type));
    uint32_t len = static_cast<uint32_t>(payload.size());
    out.push_back(static_cast<uint8_t>((len >> 24) & 0xFF));
    out.push_back(static_cast<uint8_t>((len >> 16) & 0xFF));
    out.push_back(static_cast<uint8_t>((len >> 8) & 0xFF));
    out.push_back(static_cast<uint8_t>(len & 0xFF));
    out.insert(out.end(), payload.begin(), payload.end());
    return out;
}

std::vector<uint8_t> encode_json(MessageType type, const nlohmann::json& obj) {
    std::string dumped = obj.dump();
    std::vector<uint8_t> payload(dumped.begin(), dumped.end());
    return encode_frame(type, payload);
}

nlohmann::json decode_json(const std::vector<uint8_t>& payload) {
    return nlohmann::json::parse(payload.begin(), payload.end());
}

std::vector<uint8_t> encode_event_binary(const MarketEvent& event) {
    std::vector<uint8_t> out;
    out.reserve(kBinaryEventBodySize);
    put_le(out, static_cast<uint64_t>(event.timestamp), 8);

    uint8_t symbol_bytes[8] = {0};
    size_t n = std::min<size_t>(8, event.symbol.size());
    for (size_t i = 0; i < n; ++i) {
        symbol_bytes[i] = static_cast<uint8_t>(event.symbol[i]);
    }
    out.insert(out.end(), symbol_bytes, symbol_bytes + 8);

    put_double_le(out, event.price);
    put_le(out, event.quantity, 4);
    out.push_back(event.side == 'S' ? 1 : 0);
    put_le(out, static_cast<uint64_t>(event.sequence_number), 8);
    return out;
}

MarketEvent decode_event_binary(const std::vector<uint8_t>& payload) {
    if (payload.size() != kBinaryEventBodySize) {
        throw std::runtime_error("binary event payload has wrong size");
    }
    MarketEvent event;
    const uint8_t* p = payload.data();
    event.timestamp = static_cast<int64_t>(get_le(p, 8));
    p += 8;

    size_t symbol_len = 0;
    while (symbol_len < 8 && p[symbol_len] != 0) {
        ++symbol_len;
    }
    event.symbol.assign(reinterpret_cast<const char*>(p), symbol_len);
    p += 8;

    event.price = get_double_le(p);
    p += 8;
    event.quantity = static_cast<uint32_t>(get_le(p, 4));
    p += 4;
    event.side = (*p == 1) ? 'S' : 'B';
    p += 1;
    event.sequence_number = static_cast<int64_t>(get_le(p, 8));
    return event;
}

std::pair<MarketEvent, int64_t> decode_event(MessageType type, const std::vector<uint8_t>& payload) {
    if (payload.size() < kDispatchPrefixSize) {
        throw std::runtime_error("event payload too short for dispatch prefix");
    }
    int64_t dispatched_at_ns = static_cast<int64_t>(get_le(payload.data(), 8));
    std::vector<uint8_t> body(payload.begin() + kDispatchPrefixSize, payload.end());

    if (type == MessageType::EventBinary) {
        return {decode_event_binary(body), dispatched_at_ns};
    }
    if (type == MessageType::EventJson) {
        nlohmann::json d = decode_json(body);
        MarketEvent event;
        event.sequence_number = d.at("sequence_number").get<int64_t>();
        event.timestamp = d.at("timestamp").get<int64_t>();
        event.symbol = d.at("symbol").get<std::string>();
        event.price = d.at("price").get<double>();
        event.quantity = d.at("quantity").get<uint32_t>();
        event.side = d.at("side").get<std::string>()[0];
        return {event, dispatched_at_ns};
    }
    throw std::runtime_error("not an event message type");
}

void FrameReader::feed(const uint8_t* data, size_t len, const FrameHandler& on_frame) {
    buffer_.insert(buffer_.end(), data, data + len);

    size_t pos = 0;
    while (buffer_.size() - pos >= kHeaderSize) {
        uint8_t type_byte = buffer_[pos];
        uint32_t payload_len = (static_cast<uint32_t>(buffer_[pos + 1]) << 24) |
                                (static_cast<uint32_t>(buffer_[pos + 2]) << 16) |
                                (static_cast<uint32_t>(buffer_[pos + 3]) << 8) |
                                static_cast<uint32_t>(buffer_[pos + 4]);
        size_t total = kHeaderSize + payload_len;
        if (buffer_.size() - pos < total) {
            break;
        }
        std::vector<uint8_t> payload(buffer_.begin() + pos + kHeaderSize, buffer_.begin() + pos + total);
        on_frame(static_cast<MessageType>(type_byte), std::move(payload));
        pos += total;
    }
    if (pos > 0) {
        buffer_.erase(buffer_.begin(), buffer_.begin() + pos);
    }
}

}  // namespace pulsex
