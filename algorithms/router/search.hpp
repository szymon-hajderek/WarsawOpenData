// Dijkstra on expected time. An edge costs walk / walk speed + bike / bike speed + wait, with the speeds of
// the query, so the path is optimal for them. A search starts from seeds (each with the cost of reaching it)
// and either covers the whole graph or stops once the cheapest target is certain.
#pragma once

#include <algorithm>
#include <cstdint>
#include <functional>
#include <limits>
#include <optional>
#include <span>
#include <utility>
#include <vector>

#include "graph.hpp"

constexpr double kInf = std::numeric_limits<double>::infinity();
constexpr std::uint32_t kNone = std::numeric_limits<std::uint32_t>::max();

// A start or an end of a search: a node plus the cost of the segment to it (seed) or from it (target).
struct End {
    std::uint32_t node;
    double cost = 0, walk = 0, wait = 0;
};

// Buffers are reused between runs; only the nodes a run touched are reset. One Search per thread.
class Search {
public:
    Search(const Graph& g, bool keep_path) : g_(g), cost_(g.n, kInf), walk_(g.n), bike_(g.n), wait_(g.n) {
        if (keep_path) from_.resize(g.n), via_.resize(g.n);
    }

    // Returns the index of the cheapest target, if one is reached. Without targets it covers the whole graph.
    std::optional<std::size_t> run(std::span<const End> seeds, const Speeds& speeds, std::span<const End> targets = {}) {
        for (const auto v : touched_) cost_[v] = kInf;
        touched_.clear();
        heap_.clear();
        for (const auto& s : seeds) {
            if (s.cost >= cost_[s.node]) continue;
            if (cost_[s.node] == kInf) touched_.push_back(s.node);
            cost_[s.node] = s.cost, walk_[s.node] = s.walk, bike_[s.node] = 0, wait_[s.node] = s.wait;
            if (!from_.empty()) from_[s.node] = kNone;
            heap_.emplace_back(s.cost, s.node);
        }
        std::ranges::make_heap(heap_, std::greater{});
        double best = kInf;
        std::optional<std::size_t> hit;
        while (!heap_.empty()) {
            std::ranges::pop_heap(heap_, std::greater{});
            const auto [c, u] = heap_.back();
            heap_.pop_back();
            if (c > cost_[u]) continue;  // stale entry
            if (c >= best) break;        // no target can get cheaper
            for (std::size_t t = 0; t < targets.size(); ++t)
                if (targets[t].node == u && c + targets[t].cost < best) best = c + targets[t].cost, hit = t;
            for (auto e = g_.offset[u]; e < g_.offset[u + 1]; ++e) {
                const auto v = g_.target[e];
                if (const double nc = c + speeds.cost(g_, e); nc < cost_[v]) {
                    if (cost_[v] == kInf) touched_.push_back(v);
                    cost_[v] = nc;
                    walk_[v] = walk_[u] + g_.walk[e];
                    bike_[v] = bike_[u] + g_.bike[e];
                    wait_[v] = wait_[u] + g_.wait[e];
                    if (!from_.empty()) from_[v] = u, via_[v] = e;
                    heap_.emplace_back(nc, v);
                    std::ranges::push_heap(heap_, std::greater{});
                }
            }
        }
        return hit;
    }

    [[nodiscard]] bool reached(std::uint32_t v) const { return cost_[v] < kInf; }
    [[nodiscard]] double cost(std::uint32_t v) const { return cost_[v]; }
    [[nodiscard]] double walk(std::uint32_t v) const { return walk_[v]; }
    [[nodiscard]] double bike(std::uint32_t v) const { return bike_[v]; }
    [[nodiscard]] double wait(std::uint32_t v) const { return wait_[v]; }

    // Edges of the cheapest path from its seed to v, in travel order, as (from node, edge). Needs keep_path.
    [[nodiscard]] std::vector<std::pair<std::uint32_t, std::uint32_t>> path_to(std::uint32_t v) const {
        std::vector<std::pair<std::uint32_t, std::uint32_t>> edges;
        for (; from_[v] != kNone; v = from_[v]) edges.emplace_back(from_[v], via_[v]);
        std::ranges::reverse(edges);
        return edges;
    }

private:
    const Graph& g_;
    std::vector<double> cost_, walk_, bike_, wait_;
    std::vector<std::uint32_t> from_, via_, touched_;
    std::vector<std::pair<double, std::uint32_t>> heap_;
};
