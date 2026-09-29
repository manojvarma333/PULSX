#pragma once
#include <chrono>

namespace pulsex {

struct SystemUsage {
    double cpu_usage = 0.0;     // percent, since last sample() call
    double memory_usage = 0.0;  // percent of total system RAM (RSS-based)
};

// Linux-only (reads /proc/self/stat, /proc/self/status, /proc/meminfo) -- the C++ worker
// only ever runs on Linux/WSL2 in this project (built via Docker's gcc image).
class SystemUsageSampler {
public:
    SystemUsageSampler();
    SystemUsage sample();

private:
    long long read_cpu_ticks() const;
    double read_memory_percent() const;

    std::chrono::steady_clock::time_point last_sample_time_;
    long long last_cpu_ticks_ = 0;
};

}  // namespace pulsex
