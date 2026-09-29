#include "pulsex/strategies.hpp"

#include <cmath>
#include <numeric>
#include <random>
#include <stdexcept>

namespace pulsex {

nlohmann::json PassThroughStrategy::process(const MarketEvent& event) {
    return {{"symbol", event.symbol}, {"price", event.price}};
}

MovingAverageStrategy::MovingAverageStrategy(size_t window) : window_(window) {
    if (window_ == 0) {
        throw std::invalid_argument("window must be > 0");
    }
}

nlohmann::json MovingAverageStrategy::process(const MarketEvent& event) {
    auto& prices = prices_by_symbol_[event.symbol];
    prices.push_back(event.price);
    if (prices.size() > window_) {
        prices.pop_front();
    }
    double sum = std::accumulate(prices.begin(), prices.end(), 0.0);
    double average = sum / static_cast<double>(prices.size());
    return {{"symbol", event.symbol}, {"moving_average", average}, {"window_size", prices.size()}};
}

nlohmann::json StatisticsStrategy::process(const MarketEvent& event) {
    auto& stats = stats_by_symbol_[event.symbol];
    stats.count += 1;
    double delta = event.price - stats.mean;
    stats.mean += delta / static_cast<double>(stats.count);
    double delta2 = event.price - stats.mean;
    stats.m2 += delta * delta2;
    double variance = stats.count > 0 ? stats.m2 / static_cast<double>(stats.count) : 0.0;
    return {
        {"symbol", event.symbol},
        {"mean", stats.mean},
        {"variance", variance},
        {"std_dev", std::sqrt(variance)},
        {"count", stats.count},
    };
}

CpuStressStrategy::CpuStressStrategy(long long iterations) : iterations_(iterations) {
    if (iterations_ < 0) {
        throw std::invalid_argument("iterations must be >= 0");
    }
}

nlohmann::json CpuStressStrategy::process(const MarketEvent& event) {
    double checksum = 0.0;
    for (long long i = 0; i < iterations_; ++i) {
        checksum += std::fmod(event.price * static_cast<double>(i), 97.0);
    }
    return {{"symbol", event.symbol}, {"checksum", checksum}};
}

FailureSimulationStrategy::FailureSimulationStrategy(double failure_probability, unsigned seed)
    : failure_probability_(failure_probability), rng_(seed) {
    if (failure_probability_ < 0.0 || failure_probability_ > 1.0) {
        throw std::invalid_argument("failure_probability must be between 0 and 1");
    }
}

nlohmann::json FailureSimulationStrategy::process(const MarketEvent& event) {
    if (dist_(rng_) < failure_probability_) {
        throw std::runtime_error("simulated failure processing sequence " + std::to_string(event.sequence_number));
    }
    return {{"symbol", event.symbol}, {"price", event.price}};
}

std::unique_ptr<Strategy> create_strategy(const std::string& name, const nlohmann::json& kwargs) {
    if (name == "passthrough") {
        return std::make_unique<PassThroughStrategy>();
    }
    if (name == "moving_average") {
        size_t window = kwargs.value("window", 20);
        return std::make_unique<MovingAverageStrategy>(window);
    }
    if (name == "statistics") {
        return std::make_unique<StatisticsStrategy>();
    }
    if (name == "cpu_stress") {
        long long iterations = kwargs.value("iterations", 10000LL);
        return std::make_unique<CpuStressStrategy>(iterations);
    }
    if (name == "failure") {
        double probability = kwargs.value("failure_probability", 0.05);
        unsigned seed = kwargs.value("seed", std::random_device{}());
        return std::make_unique<FailureSimulationStrategy>(probability, seed);
    }
    throw std::invalid_argument("unknown strategy: " + name);
}

}  // namespace pulsex
