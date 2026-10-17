// The street graph of one mode, as written by algorithms/street_graph.py (file format SMG4, README.md).
#pragma once

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string_view>
#include <vector>

// Edge flags, as in algorithms/street_model.py.
constexpr std::uint8_t kElevator = 1, kMetro = 8, kSteps = 16;

struct Graph {
    std::uint32_t n = 0, m = 0, p = 0, access_k = 0;            // nodes, edges, fixed points
    float walk_speed = 0, bike_speed = 0, access_extra_m = 0, max_snap_m = 0;
    std::vector<std::uint32_t> offset, target, out_node, in_node;  // CSR; the fixed points' virtual nodes
    std::vector<float> walk, bike, wait, entry_wait;
    std::vector<std::uint8_t> flags, active, usable;
    std::vector<double> lon, lat;
};

// What a search minimises: walk / walk speed + bike / bike speed + wait (s).
struct Speeds {
    double walk, bike;
    [[nodiscard]] double cost(const Graph& g, std::uint32_t e) const {
        return g.walk[e] / walk + g.bike[e] / bike + g.wait[e];
    }
};

inline Speeds default_speeds(const Graph& g) { return {g.walk_speed, g.bike_speed}; }

template <class T>
void read_into(std::ifstream& in, std::vector<T>& v, std::size_t count) {
    v.resize(count);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(T)));
}

inline Graph load(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    char magic[4]{};
    in.read(magic, sizeof magic);
    if (!in || std::string_view(magic, sizeof magic) != "SMG4")
        throw std::runtime_error("not a street graph file (SMG4): " + path.string());
    Graph g;
    for (auto* x : {&g.n, &g.m, &g.p, &g.access_k}) in.read(reinterpret_cast<char*>(x), sizeof *x);
    for (auto* x : {&g.walk_speed, &g.bike_speed, &g.access_extra_m, &g.max_snap_m})
        in.read(reinterpret_cast<char*>(x), sizeof *x);
    read_into(in, g.offset, g.n + 1);
    read_into(in, g.target, g.m);
    read_into(in, g.walk, g.m);
    read_into(in, g.bike, g.m);
    read_into(in, g.wait, g.m);
    read_into(in, g.flags, g.m);
    read_into(in, g.out_node, g.p);
    read_into(in, g.in_node, g.p);
    read_into(in, g.active, g.p);
    read_into(in, g.lon, g.n);
    read_into(in, g.lat, g.n);
    read_into(in, g.usable, g.n);
    read_into(in, g.entry_wait, g.n);
    if (!in) throw std::runtime_error("truncated street graph file: " + path.string());
    return g;
}
