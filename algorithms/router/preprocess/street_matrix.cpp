// All-pairs street paths: one Dijkstra per point, summing length and wait along the cheapest path.
// Usage: street_matrix <graph.bin> <out.bin> [--threads N]. File formats: README.md.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <limits>
#include <print>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace {

constexpr double kInf = std::numeric_limits<double>::infinity();
constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();

struct Graph {
    std::uint32_t n = 0, m = 0, p = 0;
    std::vector<std::uint32_t> offset, target, out_node, in_node;
    std::vector<double> cost;
    std::vector<float> length, wait;
    std::vector<std::uint8_t> active;
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
    if (!in || std::string_view(magic, sizeof magic) != "SMG1")
        throw std::runtime_error("not a street graph file: " + path.string());
    Graph g;
    for (auto* x : {&g.n, &g.m, &g.p}) in.read(reinterpret_cast<char*>(x), sizeof *x);
    read_into(in, g.offset, g.n + 1);
    read_into(in, g.target, g.m);
    read_into(in, g.cost, g.m);
    read_into(in, g.length, g.m);
    read_into(in, g.wait, g.m);
    read_into(in, g.out_node, g.p);
    read_into(in, g.in_node, g.p);
    read_into(in, g.active, g.p);
    if (!in) throw std::runtime_error("truncated street graph file: " + path.string());
    return g;
}

// One-to-all Dijkstra on expected time. Buffers are reused between runs.
class Search {
public:
    explicit Search(const Graph& g) : g_(g), cost_(g.n), length_(g.n), wait_(g.n) {}

    void run(std::uint32_t source) {
        std::ranges::fill(cost_, kInf);
        cost_[source] = length_[source] = wait_[source] = 0.0;
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
                    heap_.emplace_back(nc, v);
                    std::ranges::push_heap(heap_, std::greater{});
                }
            }
        }
    }

    [[nodiscard]] bool reached(std::uint32_t v) const { return cost_[v] < kInf; }
    [[nodiscard]] double length(std::uint32_t v) const { return length_[v]; }
    [[nodiscard]] double wait(std::uint32_t v) const { return wait_[v]; }

private:
    const Graph& g_;
    std::vector<double> cost_, length_, wait_;
    std::vector<std::pair<double, std::uint32_t>> heap_;
};

void write_at(int fd, std::span<const float> data, std::uint64_t offset) {
    auto bytes = std::as_bytes(data);
    while (!bytes.empty()) {
        const auto k = ::pwrite(fd, bytes.data(), bytes.size(), static_cast<off_t>(offset));
        if (k <= 0) throw std::runtime_error("write failed");
        bytes = bytes.subspan(static_cast<std::size_t>(k));
        offset += static_cast<std::uint64_t>(k);
    }
}

}  // namespace

int main(int argc, char** argv) try {
    std::vector<std::string_view> args(argv + 1, argv + argc);
    unsigned threads = std::max(1u, std::thread::hardware_concurrency());
    if (auto it = std::ranges::find(args, "--threads"); it != args.end() && it + 1 != args.end()) {
        threads = static_cast<unsigned>(std::stoul(std::string(*(it + 1))));
        args.erase(it, it + 2);
    }
    if (args.size() != 2) {
        std::println(stderr, "usage: street_matrix <graph.bin> <out.bin> [--threads N]");
        return 2;
    }

    const auto t0 = std::chrono::steady_clock::now();
    const Graph g = load(args[0]);
    const std::uint64_t p = g.p;
    const int fd = ::open(std::string(args[1]).c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd < 0 || ::ftruncate(fd, static_cast<off_t>(2 * p * p * sizeof(float))) != 0)
        throw std::runtime_error("cannot create " + std::string(args[1]));

    std::atomic<std::uint32_t> next{0}, done{0};
    auto worker = [&] {
        Search search(g);
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
} catch (const std::exception& e) {
    std::println(stderr, "error: {}", e.what());
    return 1;
}
