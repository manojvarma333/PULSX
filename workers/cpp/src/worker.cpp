#include "pulsex/worker.hpp"

#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <chrono>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace pulsex {

namespace {
constexpr int kReconnectBackoffsSeconds[] = {1, 2, 4, 8, 16, 30};
constexpr size_t kReconnectBackoffsCount = sizeof(kReconnectBackoffsSeconds) / sizeof(int);
}  // namespace

PulseXWorker::PulseXWorker(std::string worker_id, std::string host, int port, std::string strategy_name,
                            nlohmann::json strategy_kwargs, double heartbeat_interval_seconds)
    : worker_id_(std::move(worker_id)),
      host_(std::move(host)),
      port_(port),
      strategy_(create_strategy(strategy_name, strategy_kwargs)),
      heartbeat_interval_seconds_(heartbeat_interval_seconds) {}

void PulseXWorker::stop() { stop_flag_.store(true); }

bool PulseXWorker::sleep_or_stop(double seconds) const {
    // Sleeps in short increments so stop() is noticed promptly instead of after a full interval.
    const double step = 0.1;
    double waited = 0.0;
    while (waited < seconds) {
        if (stop_flag_.load()) {
            return true;
        }
        double this_step = std::min(step, seconds - waited);
        std::this_thread::sleep_for(std::chrono::duration<double>(this_step));
        waited += this_step;
    }
    return stop_flag_.load();
}

void PulseXWorker::run_forever() {
    size_t attempt = 0;
    while (!stop_flag_.load()) {
        try {
            connect_and_serve();
            attempt = 0;
        } catch (const std::exception& ex) {
            std::cerr << "worker " << worker_id_ << ": connection lost (" << ex.what() << ")\n";
        }
        if (stop_flag_.load()) {
            return;
        }
        int delay = kReconnectBackoffsSeconds[std::min(attempt, kReconnectBackoffsCount - 1)];
        attempt += 1;
        std::cerr << "worker " << worker_id_ << ": reconnecting in " << delay << "s\n";
        if (sleep_or_stop(static_cast<double>(delay))) {
            return;
        }
    }
}

int PulseXWorker::connect_to_server() const {
    addrinfo hints{};
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    addrinfo* res = nullptr;

    std::string port_str = std::to_string(port_);
    int rc = getaddrinfo(host_.c_str(), port_str.c_str(), &hints, &res);
    if (rc != 0) {
        throw std::runtime_error("getaddrinfo failed: " + std::string(gai_strerror(rc)));
    }

    int sock_fd = -1;
    for (addrinfo* p = res; p != nullptr; p = p->ai_next) {
        sock_fd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (sock_fd < 0) {
            continue;
        }
        if (connect(sock_fd, p->ai_addr, p->ai_addrlen) == 0) {
            break;
        }
        close(sock_fd);
        sock_fd = -1;
    }
    freeaddrinfo(res);

    if (sock_fd < 0) {
        throw std::runtime_error("failed to connect to " + host_ + ":" + port_str);
    }

    timeval tv{1, 0};
    setsockopt(sock_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    return sock_fd;
}

void PulseXWorker::connect_and_serve() {
    int sock_fd = connect_to_server();
    try {
        register_worker(sock_fd);
        std::thread heartbeat_thread(&PulseXWorker::heartbeat_loop, this, sock_fd);
        receive_loop(sock_fd);
        stop_flag_.store(true);  // receive_loop only returns on stop/disconnect; wake the heartbeat thread too
        heartbeat_thread.join();
    } catch (...) {
        close(sock_fd);
        throw;
    }
    close(sock_fd);
}

void PulseXWorker::send_frame(int sock_fd, const std::vector<uint8_t>& frame) {
    std::lock_guard<std::mutex> lock(send_mutex_);
    size_t sent = 0;
    while (sent < frame.size()) {
        ssize_t n = send(sock_fd, frame.data() + sent, frame.size() - sent, 0);
        if (n <= 0) {
            throw std::runtime_error("send() failed");
        }
        sent += static_cast<size_t>(n);
    }
}

void PulseXWorker::register_worker(int sock_fd) {
    char hostname_buf[256] = {0};
    gethostname(hostname_buf, sizeof(hostname_buf) - 1);

    nlohmann::json registration = {
        {"worker_id", worker_id_},
        {"hostname", std::string(hostname_buf)},
        {"language", "cpp"},
        {"version", "1.0"},
    };
    send_frame(sock_fd, encode_json(MessageType::Register, registration));

    FrameReader reader;
    std::array<uint8_t, 4096> buf{};
    bool acked = false;
    while (!acked) {
        ssize_t n = recv(sock_fd, buf.data(), buf.size(), 0);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                continue;
            }
            throw std::runtime_error("recv() failed during registration");
        }
        if (n == 0) {
            throw std::runtime_error("server closed connection during registration");
        }
        reader.feed(buf.data(), static_cast<size_t>(n), [&](MessageType type, std::vector<uint8_t> payload) {
            if (type == MessageType::RegisterAck) {
                acked = true;
            }
        });
    }
}

void PulseXWorker::heartbeat_loop(int sock_fd) {
    while (!stop_flag_.load()) {
        SystemUsage usage = usage_sampler_.sample();
        nlohmann::json heartbeat = {
            {"worker_id", worker_id_},
            {"cpu_usage", usage.cpu_usage},
            {"memory_usage", usage.memory_usage},
            {"events_processed", events_processed_.load()},
            {"events_failed", events_failed_.load()},
        };
        long long last_seq = last_processed_sequence_.load();
        heartbeat["last_processed_sequence"] = (last_seq < 0) ? nlohmann::json(nullptr) : nlohmann::json(last_seq);

        try {
            send_frame(sock_fd, encode_json(MessageType::Heartbeat, heartbeat));
        } catch (const std::exception&) {
            return;
        }
        if (sleep_or_stop(heartbeat_interval_seconds_)) {
            return;
        }
    }
}

void PulseXWorker::receive_loop(int sock_fd) {
    FrameReader reader;
    std::array<uint8_t, 65536> buf{};
    while (!stop_flag_.load()) {
        ssize_t n = recv(sock_fd, buf.data(), buf.size(), 0);
        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                continue;
            }
            throw std::runtime_error("recv() failed");
        }
        if (n == 0) {
            throw std::runtime_error("server closed connection");
        }
        int64_t received_at_ns = now_ns();
        reader.feed(buf.data(), static_cast<size_t>(n), [&](MessageType type, std::vector<uint8_t> payload) {
            if (type == MessageType::EventJson || type == MessageType::EventBinary) {
                handle_event(sock_fd, type, payload, received_at_ns);
            }
        });
    }
}

void PulseXWorker::handle_event(int sock_fd, MessageType type, const std::vector<uint8_t>& payload,
                                 int64_t received_at_ns) {
    auto [event, dispatched_at_ns] = decode_event(type, payload);
    int64_t decoded_at_ns = now_ns();

    int64_t processing_started_ns = now_ns();
    bool success = true;
    nlohmann::json result = nullptr;
    std::string error;
    try {
        result = strategy_->process(event);
    } catch (const std::exception& ex) {
        success = false;
        error = ex.what();
    }
    int64_t processing_completed_ns = now_ns();

    if (success) {
        events_processed_.fetch_add(1);
    } else {
        events_failed_.fetch_add(1);
    }
    last_processed_sequence_.store(event.sequence_number);

    nlohmann::json message = {
        {"worker_id", worker_id_},
        {"sequence_number", event.sequence_number},
        {"success", success},
        {"result", result},
        {"error", success ? nlohmann::json(nullptr) : nlohmann::json(error)},
        {"dispatched_at_ns", dispatched_at_ns},
        {"received_at_ns", received_at_ns},
        {"decoded_at_ns", decoded_at_ns},
        {"processing_started_ns", processing_started_ns},
        {"processing_completed_ns", processing_completed_ns},
    };
    try {
        send_frame(sock_fd, encode_json(MessageType::Result, message));
    } catch (const std::exception& ex) {
        std::cerr << "worker " << worker_id_ << ": failed to send result for sequence "
                  << event.sequence_number << ": " << ex.what() << "\n";
    }
}

}  // namespace pulsex
