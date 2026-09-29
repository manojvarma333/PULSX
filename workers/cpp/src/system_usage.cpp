#include "pulsex/system_usage.hpp"

#include <fstream>
#include <sstream>
#include <string>
#include <unistd.h>

namespace pulsex {

SystemUsageSampler::SystemUsageSampler() {
    last_sample_time_ = std::chrono::steady_clock::now();
    last_cpu_ticks_ = read_cpu_ticks();
}

SystemUsage SystemUsageSampler::sample() {
    auto now = std::chrono::steady_clock::now();
    long long cpu_ticks = read_cpu_ticks();
    double elapsed_seconds = std::chrono::duration<double>(now - last_sample_time_).count();
    long clock_ticks_per_sec = sysconf(_SC_CLK_TCK);

    double cpu_percent = 0.0;
    if (elapsed_seconds > 0 && clock_ticks_per_sec > 0) {
        double delta_ticks = static_cast<double>(cpu_ticks - last_cpu_ticks_);
        cpu_percent = (delta_ticks / static_cast<double>(clock_ticks_per_sec)) / elapsed_seconds * 100.0;
    }

    last_sample_time_ = now;
    last_cpu_ticks_ = cpu_ticks;

    return {cpu_percent, read_memory_percent()};
}

long long SystemUsageSampler::read_cpu_ticks() const {
    std::ifstream stat("/proc/self/stat");
    if (!stat.is_open()) {
        return 0;
    }
    std::string line;
    std::getline(stat, line);

    // Process name (2nd field) is parenthesized and may itself contain spaces/parens,
    // so skip past the LAST ')' before splitting the remaining whitespace-separated fields.
    auto close_paren = line.rfind(')');
    if (close_paren == std::string::npos || close_paren + 2 >= line.size()) {
        return 0;
    }
    std::istringstream rest(line.substr(close_paren + 2));
    std::vector<std::string> fields;
    std::string token;
    while (rest >> token) {
        fields.push_back(token);
    }
    // `rest` starts at field #3 (state); utime is field #14, stime is field #15 overall,
    // i.e. indices 11 and 12 in this 0-based vector.
    if (fields.size() < 13) {
        return 0;
    }
    long long utime = std::stoll(fields[11]);
    long long stime = std::stoll(fields[12]);
    return utime + stime;
}

double SystemUsageSampler::read_memory_percent() const {
    long long vm_rss_kb = 0;
    long long mem_total_kb = 0;

    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (line.rfind("VmRSS:", 0) == 0) {
            std::istringstream iss(line.substr(6));
            iss >> vm_rss_kb;
            break;
        }
    }

    std::ifstream meminfo("/proc/meminfo");
    while (std::getline(meminfo, line)) {
        if (line.rfind("MemTotal:", 0) == 0) {
            std::istringstream iss(line.substr(9));
            iss >> mem_total_kb;
            break;
        }
    }

    if (mem_total_kb <= 0) {
        return 0.0;
    }
    return static_cast<double>(vm_rss_kb) / static_cast<double>(mem_total_kb) * 100.0;
}

}  // namespace pulsex
