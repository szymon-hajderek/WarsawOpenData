// Street paths between points: one Dijkstra per point, summing length and wait along the cheapest path.
// Matrix:  street_matrix <graph.bin> <out.bin> [--threads N]
// Paths:   street_matrix <graph.bin> --route I J [--route I J ...]   (one JSON line per route on stdout)
// File formats: README.md.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <format>
#include <fstream>
#include <functional>
#include <limits>
#include <print>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace {

constexpr double kInf = std::numeric_limits<double>::infinity();
constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();
constexpr std::uint32_t kNone = std::numeric_limits<std::uint32_t>::max();
// Edge flags, as written by street_matrix.py.
constexpr std::uint8_t kElevator = 1, kMetro = 8;

struct Graph {
    std::uint32_t n = 0, m = 0, p = 0;
    std::vector<std::uint32_t> offset, target, out_node, in_node;
    std::vector<double> cost;
    std::vector<float> length, wait, lon, lat;
    std::vector<std::uint8_t> flags, active;
};

template <class T>
void read_into(std::ifstream& in, std::vector<T>& v, std::size_t count) {
    v.resize(count);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(T)));
}

Graph load(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    char magic[4]{};
    in.read(magic, sizeof magic);
    if (!in || std::string_view(magic, sizeof magic) != "SMG2")
        throw std::runtime_error("not a street graph file (SMG2): " + path.string());
    Graph g;
    for (auto* x : {&g.n, &g.m, &g.p}) in.read(reinterpret_cast<char*>(x), sizeof *x);
    read_into(in, g.offset, g.n + 1);
    read_into(in, g.target, g.m);
    read_into(in, g.cost, g.m);
    read_into(in, g.length, g.m);
    read_into(in, g.wait, g.m);
    read_into(in, g.flags, g.m);
    read_into(in, g.out_node, g.p);
    read_into(in, g.in_node, g.p);
    read_into(in, g.active, g.p);
    read_into(in, g.lon, g.n);
    read_into(in, g.lat, g.n);
    if (!in) throw std::runtime_error("truncated street graph file: " + path.string());
    return g;
}

// One-to-all Dijkstra on expected time. Buffers are reused between runs.
// With keep_path it also records the edge into each node, so paths can be rebuilt.
class Search {
public:
    Search(const Graph& g, bool keep_path) : g_(g), cost_(g.n), length_(g.n), wait_(g.n) {
        if (keep_path) from_.resize(g.n), via_.resize(g.n);
    }

    void run(std::uint32_t source) {
        std::ranges::fill(cost_, kInf);
        cost_[source] = length_[source] = wait_[source] = 0.0;
        if (!from_.empty()) from_[source] = kNone;
        heap_.assign({{0.0, source}});
        while (!heap_.empty()) {
            std::ranges::pop_heap(heap_, std::greater{});
            const auto [c, u] = heap_.back();
            heap_.pop_back();
            if (c > cost_[u]) continue;  // stale entry
            for (auto e = g_.offset[u]; e < g_.offset[u + 1]; ++e) {
                const auto v = g_.target[e];
                if (const double nc = c + g_.cost[e]; nc < cost_[v]) {
                    cost_[v] = nc;
                    length_[v] = length_[u] + g_.length[e];
                    wait_[v] = wait_[u] + g_.wait[e];
                    if (!from_.empty()) from_[v] = u, via_[v] = e;
                    heap_.emplace_back(nc, v);
                    std::ranges::push_heap(heap_, std::greater{});
                }
            }
        }
    }

    [[nodiscard]] bool reached(std::uint32_t v) const { return cost_[v] < kInf; }
    [[nodiscard]] double cost(std::uint32_t v) const { return cost_[v]; }
    [[nodiscard]] double length(std::uint32_t v) const { return length_[v]; }
    [[nodiscard]] double wait(std::uint32_t v) const { return wait_[v]; }

    // Edges of the cheapest path from the last source to v, in travel order (needs keep_path).
    [[nodiscard]] std::vector<std::pair<std::uint32_t, std::uint32_t>> path_to(std::uint32_t v) const {
        std::vector<std::pair<std::uint32_t, std::uint32_t>> edges;  // (from node, edge)
        for (; from_[v] != kNone; v = from_[v]) edges.emplace_back(from_[v], via_[v]);
        std::ranges::reverse(edges);
        return edges;
    }

private:
    const Graph& g_;
    std::vector<double> cost_, length_, wait_;
    std::vector<std::uint32_t> from_, via_;
    std::vector<std::pair<double, std::uint32_t>> heap_;
};

std::string lonlat(const Graph& g, std::uint32_t v) { return std::format("[{:.5f},{:.5f}]", g.lon[v], g.lat[v]); }

// One JSON line: totals, the path as [lon, lat] (about 1 m precision, repeated points dropped),
// the elevators used and the metro entrance segments (at the street end).
std::string route_json(const Graph& g, Search& search, std::uint32_t i, std::uint32_t j) {
    const auto head = std::format(R"({{"from":{},"to":{})", i, j);
    if (i >= g.p || j >= g.p) return head + R"(,"error":"point index out of range"})";
    search.run(g.out_node[i]);
    const auto t = g.in_node[j];
    if (!search.reached(t)) return head + R"(,"error":"no path"})";
    std::string path = lonlat(g, g.out_node[i]), elevators, metro;
    auto add = [](std::string& list, const std::string& point) {
        if (!list.ends_with(point)) list += (list.empty() ? "" : ",") + point;
    };
    for (const auto& [u, e] : search.path_to(t)) {
        const auto v = g.target[e];
        add(path, lonlat(g, v));
        const auto street_end = u < g.n - 2 * g.p ? u : v;  // the non-virtual end of an access segment
        if (g.flags[e] & kElevator) add(elevators, lonlat(g, street_end));
        if (g.flags[e] & kMetro) add(metro, lonlat(g, street_end));
    }
    return head + std::format(R"(,"seconds":{:.1f},"distance_m":{:.1f},"wait_s":{:.1f},"path":[{}],)"
                              R"("elevators":[{}],"metro_entrances":[{}]}})",
                              search.cost(t), search.length(t), search.wait(t), path, elevators, metro);
}

void write_at(int fd, std::span<const float> data, std::uint64_t offset) {
    auto bytes = std::as_bytes(data);
    while (!bytes.empty()) {
        const auto k = ::pwrite(fd, bytes.data(), bytes.size(), static_cast<off_t>(offset));
        if (k <= 0) throw std::runtime_error("write failed");
        bytes = bytes.subspan(static_cast<std::size_t>(k));
        offset += static_cast<std::uint64_t>(k);
    }
}

void matrix(const Graph& g, const std::string& out, unsigned threads) {
    const auto t0 = std::chrono::steady_clock::now();
    const std::uint64_t p = g.p;
    const int fd = ::open(out.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd < 0 || ::ftruncate(fd, static_cast<off_t>(2 * p * p * sizeof(float))) != 0)
        throw std::runtime_error("cannot create " + out);

    std::atomic<std::uint32_t> next{0}, done{0};
    auto worker = [&] {
        Search search(g, false);
        std::vector<float> dist(p), wait(p);
        for (std::uint32_t i = next++; i < p; i = next++) {
            std::ranges::fill(dist, kNaN);
            std::ranges::fill(wait, kNaN);
            if (g.active[i]) {
                search.run(g.out_node[i]);
                for (std::uint32_t j = 0; j < p; ++j) {
                    if (g.active[j] && search.reached(g.in_node[j])) {
                        dist[j] = static_cast<float>(search.length(g.in_node[j]));
                        wait[j] = static_cast<float>(search.wait(g.in_node[j]));
                    }
                }
                dist[i] = wait[i] = 0.0f;
            }
            write_at(fd, dist, i * p * sizeof(float));
            write_at(fd, wait, (p * p + i * p) * sizeof(float));
            if (const auto k = ++done; k % 100 == 0 || k == p) {
                const std::chrono::duration<double> s = std::chrono::steady_clock::now() - t0;
                std::print(stderr, "\r{}/{} sources, {:.0f} s", k, p, s.count());
            }
        }
    };
    {
        std::vector<std::jthread> pool;
        for (unsigned t = 0; t < threads; ++t) pool.emplace_back(worker);
    }
    ::close(fd);
    const std::chrono::duration<double> s = std::chrono::steady_clock::now() - t0;
    std::println(stderr, "\ndone: {} points, {} nodes, {} edges, {} threads, {:.1f} s", p, g.n, g.m, threads, s.count());
}

}  // namespace

int main(int argc, char** argv) try {
    std::vector<std::string_view> args(argv + 1, argv + argc);
    unsigned threads = std::max(1u, std::thread::hardware_concurrency());
    std::vector<std::pair<std::uint32_t, std::uint32_t>> routes;
    for (auto it = args.begin(); it != args.end();) {
        if (*it == "--threads" && it + 1 != args.end()) {
            threads = static_cast<unsigned>(std::stoul(std::string(it[1])));
            it = args.erase(it, it + 2);
        } else if (*it == "--route" && args.end() - it >= 3) {
            routes.emplace_back(std::stoul(std::string(it[1])), std::stoul(std::string(it[2])));
            it = args.erase(it, it + 3);
        } else {
            ++it;
        }
    }
    if (args.size() != (routes.empty() ? 2u : 1u)) {
        std::println(stderr, "usage: street_matrix <graph.bin> <out.bin> [--threads N]\n"
                             "       street_matrix <graph.bin> --route I J [--route I J ...]");
        return 2;
    }
    const Graph g = load(args[0]);
    if (routes.empty()) {
        matrix(g, std::string(args[1]), threads);
        return 0;
    }
    Search search(g, true);
    for (const auto& [i, j] : routes) std::println("{}", route_json(g, search, i, j));
} catch (const std::exception& e) {
    std::println(stderr, "error: {}", e.what());
    return 1;
}
