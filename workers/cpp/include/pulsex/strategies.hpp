#pragma once
// Simulation strategies (PRD section 16) -- mirrors strategies/*/__init__.py in Python
// so the same experiment can be run with either worker language and produce comparable
// result shapes.
#include <deque>
#include <memory>
#include <random>
#include <string>
#include <unordered_map>

#include <nlohmann/json.hpp>

#include "pulsex/protocol.hpp"

namespace pulsex {

class Strategy {
public:
    virtual ~Strategy() = default;
    virtual nlohmann::json process(const MarketEvent& event) = 0;
};

class PassThroughStrategy : public Strategy {
public:
    nlohmann::json process(const MarketEvent& event) override;
};

class MovingAverageStrategy : public Strategy {
public:
    explicit MovingAverageStrategy(size_t window = 20);
    nlohmann::json process(const MarketEvent& event) override;

private:
    size_t window_;
    std::unordered_map<std::string, std::deque<double>> prices_by_symbol_;
};

class StatisticsStrategy : public Strategy {
public:
    nlohmann::json process(const MarketEvent& event) override;

private:
    struct RunningStats {
        long long count = 0;
        double mean = 0.0;
        double m2 = 0.0;
    };
    std::unordered_map<std::string, RunningStats> stats_by_symbol_;
};

class CpuStressStrategy : public Strategy {
public:
    explicit CpuStressStrategy(long long iterations = 10000);
    nlohmann::json process(const MarketEvent& event) override;

private:
    long long iterations_;
};

class FailureSimulationStrategy : public Strategy {
public:
    explicit FailureSimulationStrategy(double failure_probability = 0.05, unsigned seed = 0);
    nlohmann::json process(const MarketEvent& event) override;

private:
    double failure_probability_;
    std::mt19937 rng_;
    std::uniform_real_distribution<double> dist_{0.0, 1.0};
};

// Factory: name is one of "passthrough" | "moving_average" | "statistics" | "cpu_stress" | "failure".
std::unique_ptr<Strategy> create_strategy(const std::string& name, const nlohmann::json& kwargs);

}  // namespace pulsex
