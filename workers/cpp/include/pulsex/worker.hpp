#pragma once
#include <atomic>
#include <mutex>
#include <string>

#include <nlohmann/json.hpp>

#include "pulsex/protocol.hpp"
#include "pulsex/strategies.hpp"
#include "pulsex/system_usage.hpp"

namespace pulsex {

// PRD section 15: Python worker's C++ counterpart. Connects to the TCP event server,
// registers, heartbeats, receives events, runs a Strategy, and reports results.
class PulseXWorker {
public:
    PulseXWorker(std::string worker_id, std::string host, int port, std::string strategy_name,
                 nlohmann::json strategy_kwargs, double heartbeat_interval_seconds);

    // Connects and serves events, reconnecting with backoff, until stop() is called.
    void run_forever();
    void stop();

private:
    void connect_and_serve();
    int connect_to_server() const;
    void register_worker(int sock_fd);
    void heartbeat_loop(int sock_fd);
    void receive_loop(int sock_fd);
    void handle_event(int sock_fd, MessageType type, const std::vector<uint8_t>& payload, int64_t received_at_ns);
    void send_frame(int sock_fd, const std::vector<uint8_t>& frame);
    bool sleep_or_stop(double seconds) const;

    std::string worker_id_;
    std::string host_;
    int port_;
    std::unique_ptr<Strategy> strategy_;
    double heartbeat_interval_seconds_;

    std::atomic<bool> stop_flag_{false};
    std::mutex send_mutex_;
    std::atomic<long long> events_processed_{0};
    std::atomic<long long> events_failed_{0};
    std::atomic<long long> last_processed_sequence_{-1};
    SystemUsageSampler usage_sampler_;
};

}  // namespace pulsex
