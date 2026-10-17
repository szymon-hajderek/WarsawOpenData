// Street paths between points: one Dijkstra per point, summing walk, bike and wait along the cheapest path.
// Matrix:  street_matrix <graph.bin> <out.bin> [--threads N]
// Paths:   street_matrix <graph.bin> --route I J [--route I J ...]   (one JSON line per route on stdout)
// Server:  street_matrix --serve <dir with graph_<mode>.bin> [--port 8090] [--threads 4]
//          GET /route?mode=walk&from=I&to=J, GET /health. The graphs stay in memory.
// File formats and API: README.md.
#include <algorithm>
#include <atomic>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <format>
#include <fstream>
#include <expected>
#include <functional>
#include <limits>
#include <map>
#include <memory>
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

#include <httplib.h>

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
    std::vector<float> walk, bike, wait, lon, lat;
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
    if (!in || std::string_view(magic, sizeof magic) != "SMG3")
        throw std::runtime_error("not a street graph file (SMG3): " + path.string());
    Graph g;
    for (auto* x : {&g.n, &g.m, &g.p}) in.read(reinterpret_cast<char*>(x), sizeof *x);
    read_into(in, g.offset, g.n + 1);
    read_into(in, g.target, g.m);
    read_into(in, g.cost, g.m);
    read_into(in, g.walk, g.m);
    read_into(in, g.bike, g.m);
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

// Dijkstra on expected time. Buffers are reused between runs; only the nodes a run touched are reset.
// With keep_path it also records the edge into each node, so paths can be rebuilt.
class Search {
public:
    Search(const Graph& g, bool keep_path)
        : g_(g), cost_(g.n, kInf), walk_(g.n), bike_(g.n), wait_(g.n) {
        if (keep_path) from_.resize(g.n), via_.resize(g.n);
    }

    // One-to-all, or stop as soon as `target` is settled.
    void run(std::uint32_t source, std::uint32_t target = kNone) {
        for (const auto v : touched_) cost_[v] = kInf;
        touched_.assign({source});
        cost_[source] = walk_[source] = bike_[source] = wait_[source] = 0.0;
        if (!from_.empty()) from_[source] = kNone;
        heap_.assign({{0.0, source}});
        while (!heap_.empty()) {
            std::ranges::pop_heap(heap_, std::greater{});
            const auto [c, u] = heap_.back();
            heap_.pop_back();
            if (c > cost_[u]) continue;  // stale entry
            if (u == target) return;
            for (auto e = g_.offset[u]; e < g_.offset[u + 1]; ++e) {
                const auto v = g_.target[e];
                if (const double nc = c + g_.cost[e]; nc < cost_[v]) {
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
    }

    [[nodiscard]] bool reached(std::uint32_t v) const { return cost_[v] < kInf; }
    [[nodiscard]] double cost(std::uint32_t v) const { return cost_[v]; }
    [[nodiscard]] double walk(std::uint32_t v) const { return walk_[v]; }
    [[nodiscard]] double bike(std::uint32_t v) const { return bike_[v]; }
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
    std::vector<double> cost_, walk_, bike_, wait_;
    std::vector<std::uint32_t> from_, via_, touched_;
    std::vector<std::pair<double, std::uint32_t>> heap_;
};

std::string lonlat(const Graph& g, std::uint32_t v) { return std::format("[{:.5f},{:.5f}]", g.lon[v], g.lat[v]); }

// One JSON object: totals, the path as [lon, lat] (about 1 m precision, repeated points dropped),
// the elevators used and the metro entrance segments (at the street end). The error is JSON too.
std::expected<std::string, std::string> route_json(const Graph& g, Search& search, std::uint32_t i, std::uint32_t j) {
    const auto head = std::format(R"({{"from":{},"to":{})", i, j);
    if (i >= g.p || j >= g.p) return std::unexpected(head + R"(,"error":"point index out of range"})");
    const auto t = g.in_node[j];
    search.run(g.out_node[i], t);
    if (!search.reached(t)) return std::unexpected(head + R"(,"error":"no path"})");
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
    return head + std::format(R"(,"seconds":{:.1f},"walk_m":{:.1f},"bike_m":{:.1f},"wait_s":{:.1f},"path":[{}],)"
                              R"("elevators":[{}],"metro_entrances":[{}]}})",
                              search.cost(t), search.walk(t), search.bike(t), search.wait(t), path, elevators, metro);
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
    if (fd < 0 || ::ftruncate(fd, static_cast<off_t>(3 * p * p * sizeof(float))) != 0)
        throw std::runtime_error("cannot create " + out);

    std::atomic<std::uint32_t> next{0}, done{0};
    auto worker = [&] {
        Search search(g, false);
        std::vector<float> walk(p), bike(p), wait(p);
        for (std::uint32_t i = next++; i < p; i = next++) {
            for (auto* row : {&walk, &bike, &wait}) std::ranges::fill(*row, kNaN);
            if (g.active[i]) {
                search.run(g.out_node[i]);
                for (std::uint32_t j = 0; j < p; ++j) {
                    if (const auto t = g.in_node[j]; g.active[j] && search.reached(t)) {
                        walk[j] = static_cast<float>(search.walk(t));
                        bike[j] = static_cast<float>(search.bike(t));
                        wait[j] = static_cast<float>(search.wait(t));
                    }
                }
                walk[i] = bike[i] = wait[i] = 0.0f;
            }
            for (std::uint64_t plane = 0; const auto* row : {&walk, &bike, &wait})
                write_at(fd, *row, (plane++ * p * p + i * p) * sizeof(float));
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

// A small HTTP server: loads the graph of every mode once and answers path queries from memory.
void serve(const std::filesystem::path& dir, int port, unsigned threads) {
    std::map<std::string, Graph, std::less<>> graphs;
    for (const auto* mode : {"walk", "bike", "accessible"})
        if (const auto file = dir / std::format("graph_{}.bin", mode); std::filesystem::exists(file))
            graphs.emplace(mode, load(file));
    if (graphs.empty()) throw std::runtime_error("no graph_<mode>.bin in " + dir.string());
    std::string modes, names, json = "application/json";  // modes: a JSON list; names: walk|bike|...
    for (const auto& [mode, g] : graphs) {
        modes += std::format("{}\"{}\"", modes.empty() ? "" : ",", mode);
        names += std::format("{}{}", names.empty() ? "" : "|", mode);
    }

    httplib::Server server;
    server.new_task_queue = [threads] { return new httplib::ThreadPool(threads); };
    server.Get("/health", [&](const httplib::Request&, httplib::Response& res) {
        res.set_content(std::format(R"({{"modes":[{}],"points":{}}})", modes, graphs.begin()->second.p), json);
    });
    server.Get("/route", [&](const httplib::Request& req, httplib::Response& res) {
        auto number = [&](const char* key) -> std::optional<std::uint32_t> {
            const auto text = req.get_param_value(key);
            std::uint32_t v{};
            const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), v);
            return ec == std::errc{} && end == text.data() + text.size() && !text.empty() ? std::optional(v) : std::nullopt;
        };
        const auto it = graphs.find(req.get_param_value("mode"));
        const auto from = number("from"), to = number("to");
        if (it == graphs.end() || !from || !to || *from >= it->second.p || *to >= it->second.p) {
            res.status = 400;
            res.set_content(std::format(R"({{"error":"use /route?mode={}&from=I&to=J with point indices 0..{}"}})",
                                        names, graphs.begin()->second.p - 1), json);
            return;
        }
        // one search buffer per worker thread and mode
        thread_local std::map<const Graph*, std::unique_ptr<Search>> searches;
        auto& search = searches[&it->second];
        if (!search) search = std::make_unique<Search>(it->second, true);
        const auto out = route_json(it->second, *search, *from, *to);
        res.status = out ? 200 : 404;
        res.set_content(out ? *out : out.error(), json);
    });
    std::println(stderr, "serving [{}] on http://127.0.0.1:{} with {} threads", modes, port, threads);
    if (!server.listen("127.0.0.1", port)) throw std::runtime_error(std::format("cannot listen on port {}", port));
}

}  // namespace

int main(int argc, char** argv) try {
    std::vector<std::string_view> args(argv + 1, argv + argc);
    std::optional<unsigned> threads;
    std::optional<std::string> serve_dir;
    int port = 8090;
    std::vector<std::pair<std::uint32_t, std::uint32_t>> routes;
    for (auto it = args.begin(); it != args.end();) {
        const auto left = args.end() - it;
        if (*it == "--threads" && left >= 2) {
            threads = static_cast<unsigned>(std::stoul(std::string(it[1])));
            it = args.erase(it, it + 2);
        } else if (*it == "--serve" && left >= 2) {
            serve_dir = std::string(it[1]);
            it = args.erase(it, it + 2);
        } else if (*it == "--port" && left >= 2) {
            port = std::stoi(std::string(it[1]));
            it = args.erase(it, it + 2);
        } else if (*it == "--route" && left >= 3) {
            routes.emplace_back(std::stoul(std::string(it[1])), std::stoul(std::string(it[2])));
            it = args.erase(it, it + 3);
        } else {
            ++it;
        }
    }
    if (serve_dir) {
        serve(*serve_dir, port, threads.value_or(4));
        return 0;
    }
    if (args.size() != (routes.empty() ? 2u : 1u)) {
        std::println(stderr, "usage: street_matrix <graph.bin> <out.bin> [--threads N]\n"
                             "       street_matrix <graph.bin> --route I J [--route I J ...]\n"
                             "       street_matrix --serve <dir> [--port 8090] [--threads 4]");
        return 2;
    }
    const Graph g = load(args[0]);
    if (routes.empty()) {
        matrix(g, std::string(args[1]), threads.value_or(std::max(1u, std::thread::hardware_concurrency())));
        return 0;
    }
    Search search(g, true);
    for (const auto& [i, j] : routes) {
        const auto out = route_json(g, search, i, j);
        std::println("{}", out ? *out : out.error());
    }
} catch (const std::exception& e) {
    std::println(stderr, "error: {}", e.what());
    return 1;
}
