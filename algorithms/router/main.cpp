// street_router: street paths for walk, bike and accessible. README.md has the API and the file formats.
//   street_router matrix <graph.bin> <out.bin> [--threads N]     every pair of the graph's fixed points
//   street_router route <graph.bin> LAT,LON LAT,LON              one path, JSON on stdout
//   street_router serve <dir> [--port 8090] [--threads 4]        HTTP: POST /route, GET /health
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <expected>
#include <filesystem>
#include <format>
#include <map>
#include <memory>
#include <print>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "graph.hpp"
#include "search.hpp"
#include "snap.hpp"

namespace {

using nlohmann::json;
constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();

// One mode: the graph and its coordinate index (the index refers to the graph, so both stay together).
struct Mode {
    Graph graph;
    Snapper snap;
    explicit Mode(const std::filesystem::path& file) : graph(load(file)), snap(graph) {}
};

struct Error {
    int status;  // HTTP status: 422 point too far, 404 no path
    std::string message;
};

// Round to `decimals` places; dividing by an exact power of ten keeps the JSON number short (21.0003, not 21.000300000000003).
double round_to(double v, int decimals) {
    const double scale = std::pow(10.0, decimals);
    return std::round(v * scale) / scale;
}
json lonlat(const Graph& g, std::uint32_t v) { return {round_to(g.lon[v], 5), round_to(g.lat[v], 5)}; }

// The path between two coordinates. Each joins up to k nearest usable nodes (snap.hpp); the access segments are
// walked, and entering the graph pays the node's entry wait (as street_model.access_edges in Python).
std::expected<json, Error> route(const Mode& mode, Search& search, double lat1, double lon1, double lat2, double lon2,
                                 const Speeds& speeds) {
    const Graph& g = mode.graph;
    double snap1 = 0, snap2 = 0;
    const auto a = mode.snap.nearest(lat1, lon1, snap1), b = mode.snap.nearest(lat2, lon2, snap2);
    for (const auto& [name, access, d] : {std::tuple{"start", &a, snap1}, std::tuple{"end", &b, snap2}})
        if (access->empty())
            return std::unexpected(Error{422, std::isinf(d) ? std::format("{} is more than {} m from the street graph", name, g.max_snap_m)
                                                            : std::format("{} is {:.0f} m from the street graph (max {} m)", name, d, g.max_snap_m)});
    std::vector<End> seeds, targets;
    for (const auto& x : a) seeds.push_back({x.node, x.dist_m / speeds.walk + g.entry_wait[x.node], x.dist_m, g.entry_wait[x.node]});
    for (const auto& x : b) targets.push_back({x.node, x.dist_m / speeds.walk, x.dist_m, 0});
    const auto hit = search.run(seeds, speeds, targets);
    if (!hit) return std::unexpected(Error{404, "no path"});
    const auto& t = targets[*hit];
    const auto edges = search.path_to(t.node);
    const auto start = edges.empty() ? t.node : edges.front().first;
    json path = json::array({{round_to(lon1, 5), round_to(lat1, 5)}, lonlat(g, start)}), elevators = json::array(),
         steps = json::array();
    bool on_steps = false;
    for (const auto& [u, e] : edges) {
        path.push_back(lonlat(g, g.target[e]));
        if (g.flags[e] & kElevator) elevators.push_back(lonlat(g, u));  // where it is boarded
        if ((g.flags[e] & kSteps) && !on_steps) steps.push_back(lonlat(g, u));  // where a flight of steps starts
        on_steps = g.flags[e] & kSteps;
    }
    path.push_back({round_to(lon2, 5), round_to(lat2, 5)});
    return json{{"seconds", round_to(search.cost(t.node) + t.cost, 1)},
                {"walk_m", round_to(search.walk(t.node) + t.walk, 1)},
                {"bike_m", round_to(search.bike(t.node), 1)},
                {"wait_s", round_to(search.wait(t.node) + t.wait, 1)},
                {"snap_m", {round_to(snap1, 1), round_to(snap2, 1)}},
                {"path", path},
                {"elevators", elevators},
                {"steps", steps}};
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

// walk_m, bike_m, wait_s between every pair of fixed points, with the default speeds: float32 (3, P, P).
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
                const End seed{g.out_node[i]};
                search.run({&seed, 1}, default_speeds(g));
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

// POST /route body: {"from": [lat, lon], "to": [lat, lon], "mode": "...", "speeds": {"walk": m/s, "bike": m/s}}.
// Keys the router does not support yet are answered with 501, so a caller can relay options as they come.
void serve(const std::filesystem::path& dir, int port, unsigned threads) {
    std::map<std::string, std::unique_ptr<Mode>, std::less<>> modes;
    for (const auto* name : {"walk", "bike", "accessible"})
        if (const auto file = dir / std::format("graph_{}.bin", name); std::filesystem::exists(file))
            modes.emplace(name, std::make_unique<Mode>(file));
    if (modes.empty()) throw std::runtime_error("no graph_<mode>.bin in " + dir.string());
    json health{{"modes", json::object()}};
    for (const auto& [name, m] : modes) health["modes"][name] = {{"nodes", m->graph.n}, {"edges", m->graph.m}};

    httplib::Server server;
    server.new_task_queue = [threads] { return new httplib::ThreadPool(threads); };
    auto reply = [](httplib::Response& res, int status, const json& body) {
        res.status = status;
        res.set_content(body.dump(), "application/json");
    };
    server.Get("/health", [&](const httplib::Request&, httplib::Response& res) { reply(res, 200, health); });
    server.Post("/route", [&](const httplib::Request& req, httplib::Response& res) {
        const auto body = json::parse(req.body, nullptr, false);
        if (!body.is_object()) return reply(res, 400, {{"error", "the body must be a JSON object"}});
        json unimplemented = json::array();
        for (const auto& [key, value] : body.items())
            if (key != "from" && key != "to" && key != "mode" && key != "speeds") unimplemented.push_back(key);
        if (const auto s = body.find("speeds"); s != body.end() && s->is_object())
            for (const auto& [key, value] : s->items())
                if (key != "walk" && key != "bike") unimplemented.push_back("speeds." + key);
        if (!unimplemented.empty())
            return reply(res, 501, {{"error", "not implemented"}, {"unimplemented", unimplemented}});
        auto point = [&](const char* key) -> std::optional<std::pair<double, double>> {
            const auto it = body.find(key);
            if (it == body.end() || !it->is_array() || it->size() != 2 || !(*it)[0].is_number() || !(*it)[1].is_number())
                return std::nullopt;
            const double lat = (*it)[0], lon = (*it)[1];
            return std::abs(lat) <= 90 && std::abs(lon) <= 180 ? std::optional(std::pair{lat, lon}) : std::nullopt;
        };
        const auto from = point("from"), to = point("to");
        const auto mode = modes.find(body.value("mode", std::string{}));
        if (!from || !to || mode == modes.end())
            return reply(res, 400, {{"error", "use {\"from\": [lat, lon], \"to\": [lat, lon], \"mode\": one of the modes in "
                                              "/health, \"speeds\": {\"walk\": m/s, \"bike\": m/s} (optional)}"}});
        const Graph& g = mode->second->graph;
        Speeds speeds = default_speeds(g);
        if (const auto s = body.find("speeds"); s != body.end()) {
            if (!s->is_object()) return reply(res, 400, {{"error", "speeds must be an object"}});
            speeds = {s->value("walk", speeds.walk), s->value("bike", speeds.bike)};
            if (!(speeds.walk > 0) || !(speeds.bike > 0)) return reply(res, 400, {{"error", "speeds must be > 0 (m/s)"}});
        }
        // one search buffer per worker thread and mode
        thread_local std::map<const Graph*, std::unique_ptr<Search>> searches;
        auto& search = searches[&g];
        if (!search) search = std::make_unique<Search>(g, true);
        const auto out = route(*mode->second, *search, from->first, from->second, to->first, to->second, speeds);
        out ? reply(res, 200, *out) : reply(res, out.error().status, {{"error", out.error().message}});
    });
    std::println(stderr, "serving {} on http://127.0.0.1:{} with {} threads", health["modes"].dump(), port, threads);
    if (!server.listen("127.0.0.1", port)) throw std::runtime_error(std::format("cannot listen on port {}", port));
}

std::pair<double, double> parse_point(std::string_view text) {
    const auto comma = text.find(',');
    if (comma == std::string_view::npos) throw std::runtime_error(std::format("expected LAT,LON, got {}", text));
    return {std::stod(std::string(text.substr(0, comma))), std::stod(std::string(text.substr(comma + 1)))};
}

}  // namespace

int main(int argc, char** argv) try {
    std::vector<std::string_view> args(argv + 1, argv + argc);
    std::optional<unsigned> threads;
    int port = 8090;
    for (auto it = args.begin(); it != args.end();) {
        if (it + 1 != args.end() && (*it == "--threads" || *it == "--port")) {
            const auto value = std::stoi(std::string(it[1]));
            if (*it == "--port") port = value;
            else threads = static_cast<unsigned>(value);
            it = args.erase(it, it + 2);
        } else {
            ++it;
        }
    }
    const auto cmd = args.empty() ? std::string_view{} : args[0];
    if (cmd == "matrix" && args.size() == 3) {
        matrix(load(args[1]), std::string(args[2]), threads.value_or(std::max(1u, std::thread::hardware_concurrency())));
    } else if (cmd == "route" && args.size() == 4) {
        const Mode mode(args[1]);
        Search search(mode.graph, true);
        const auto [lat1, lon1] = parse_point(args[2]);
        const auto [lat2, lon2] = parse_point(args[3]);
        const auto out = route(mode, search, lat1, lon1, lat2, lon2, default_speeds(mode.graph));
        std::println("{}", out ? out->dump() : json{{"error", out.error().message}}.dump());
        return out ? 0 : 1;
    } else if (cmd == "serve" && args.size() == 2) {
        serve(args[1], port, threads.value_or(4));
    } else {
        std::println(stderr, "usage: street_router matrix <graph.bin> <out.bin> [--threads N]\n"
                             "       street_router route <graph.bin> LAT,LON LAT,LON\n"
                             "       street_router serve <dir> [--port 8090] [--threads 4]");
        return 2;
    }
} catch (const std::exception& e) {
    std::println(stderr, "error: {}", e.what());
    return 1;
}
