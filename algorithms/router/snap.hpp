// Joining a coordinate to the graph: the same rule as osm.access() in Python. A point joins up to access_k
// usable nodes that are at most access_extra_m farther than the nearest one (none if that is > max_snap_m).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numbers>
#include <unordered_map>
#include <vector>

#include "graph.hpp"

// config.to_xy: local equirectangular metres around Warsaw.
inline double to_x(double lon) {
    return lon * std::numbers::pi / 180 * 6371000.0 * std::cos(52.23 * std::numbers::pi / 180);
}
inline double to_y(double lat) { return lat * std::numbers::pi / 180 * 6371000.0; }

struct Access {
    std::uint32_t node;
    double dist_m;
};

class Snapper {
public:
    explicit Snapper(const Graph& g, double cell_m = 100.0) : g_(g), cell_(cell_m) {
        for (std::uint32_t v = 0; v < g.n; ++v)
            if (g.usable[v]) cells_[key(cell(to_x(g.lon[v])), cell(to_y(g.lat[v])))].push_back(v);
    }

    // The access nodes of a point, nearest first; empty when it is too far from the graph.
    // `nearest_m` gets the distance to the nearest usable node (also when it is too far).
    [[nodiscard]] std::vector<Access> nearest(double lat, double lon, double& nearest_m) const {
        const double x = to_x(lon), y = to_y(lat);
        const auto cx = cell(x), cy = cell(y);
        std::vector<Access> found;
        nearest_m = std::numeric_limits<double>::infinity();
        // rings of cells around the point; nodes in ring r are at least (r - 1) * cell away
        for (std::int64_t r = 0; (r - 1) * cell_ <= std::min<double>(nearest_m + g_.access_extra_m, g_.max_snap_m);
             ++r) {
            for (auto dx = -r; dx <= r; ++dx) {
                for (auto dy = -r; dy <= r; ++dy) {
                    if (std::max(std::abs(dx), std::abs(dy)) != r) continue;
                    const auto it = cells_.find(key(cx + dx, cy + dy));
                    if (it == cells_.end()) continue;
                    for (const auto v : it->second) {
                        const double d = std::hypot(to_x(g_.lon[v]) - x, to_y(g_.lat[v]) - y);
                        found.push_back({v, d});
                        nearest_m = std::min(nearest_m, d);
                    }
                }
            }
        }
        if (nearest_m > g_.max_snap_m) return {};
        std::erase_if(found, [&](const Access& a) { return a.dist_m > nearest_m + g_.access_extra_m; });
        std::ranges::sort(found, {}, &Access::dist_m);
        if (found.size() > g_.access_k) found.resize(g_.access_k);
        return found;
    }

private:
    [[nodiscard]] std::int64_t cell(double metres) const { return static_cast<std::int64_t>(std::floor(metres / cell_)); }
    static std::int64_t key(std::int64_t cx, std::int64_t cy) { return cx * 4'000'000'007LL + cy; }

    const Graph& g_;
    double cell_;
    std::unordered_map<std::int64_t, std::vector<std::uint32_t>> cells_;
};
