#include <csignal>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>

#include "pulsex/worker.hpp"

namespace {
std::unique_ptr<pulsex::PulseXWorker>* g_worker_ptr = nullptr;

void handle_signal(int signum) {
    if (g_worker_ptr != nullptr && *g_worker_ptr != nullptr) {
        (*g_worker_ptr)->stop();
    }
}

struct Args {
    std::string worker_id;
    std::string host = "127.0.0.1";
    int port = 9000;
    std::string strategy = "passthrough";
    double heartbeat_interval = 5.0;
};

bool parse_args(int argc, char** argv, Args& out) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("missing value for " + arg);
            }
            return argv[++i];
        };
        if (arg == "--worker-id") {
            out.worker_id = next();
        } else if (arg == "--host") {
            out.host = next();
        } else if (arg == "--port") {
            out.port = std::stoi(next());
        } else if (arg == "--strategy") {
            out.strategy = next();
        } else if (arg == "--heartbeat-interval") {
            out.heartbeat_interval = std::stod(next());
        } else {
            std::cerr << "unknown argument: " << arg << "\n";
            return false;
        }
    }
    return !out.worker_id.empty();
}

}  // namespace

int main(int argc, char** argv) {
    Args args;
    if (!parse_args(argc, argv, args)) {
        std::cerr << "usage: pulsex_cpp_worker --worker-id <id> [--host 127.0.0.1] [--port 9000] "
                     "[--strategy passthrough|moving_average|statistics|cpu_stress|failure] "
                     "[--heartbeat-interval 5.0]\n";
        return 1;
    }

    auto worker = std::make_unique<pulsex::PulseXWorker>(
        args.worker_id, args.host, args.port, args.strategy, nlohmann::json::object(), args.heartbeat_interval);

    g_worker_ptr = &worker;
    std::signal(SIGINT, handle_signal);
    std::signal(SIGTERM, handle_signal);

    worker->run_forever();
    return 0;
}
