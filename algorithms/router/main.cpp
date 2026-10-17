// street_router: street paths for walk, bike, accessible and stroller. README.md has the API and the file formats.
//   street_router matrix <graph.bin> <out.bin> [--threads N]     every pair of the graph's fixed points
//   street_router route <graph.bin> LAT,LON LAT,LON              one path, JSON on stdout
//   street_router serve <dir> [--port 8090] [--threads 4]        HTTP: POST /route, POST /access, GET /health
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <expected>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <memory>
#include <optional>
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
#include "stations.hpp"

namespace {

using nlohmann::json;
constexpr float kNaN = std::numeric_limits<float>::quiet_NaN();
using Modes = std::map<std::string, std::unique_ptr<struct Mode>, std::less<>>;

// One mode: the graph, its reverse (for searches that end at a point), the coordinate index and where every
// location of the overlay touches this graph.
struct Mode {
    std::string name;
    Graph graph, rev;
    Snapper snap;
    std::vector<std::vector<Stations::Touch>> touches;
    Mode(std::string name_, const std::filesystem::path& file)
        : name(std::move(name_)), graph(load(file)), rev(reversed(graph)), snap(graph) {}
};

struct Error {
    int status;  // HTTP status: 400 bad request, 404 unknown id / no path, 422 point too far
    std::string message;
};

double round_to(double v, int decimals) {
    const double scale = std::pow(10.0, decimals);
    return std::round(v * scale) / scale;
}
json lonlat(double lon, double lat) { return {round_to(lon, 5), round_to(lat, 5)}; }
json lonlat(const Graph& g, std::uint32_t v) { return lonlat(g.lon[v], g.lat[v]); }

// Where a search starts or ends: a coordinate or a location, resolved to graph ends.
struct Place {
    std::vector<End> ends;
    double lat = 0, lon = 0, snap_m = 0;
    const Location* location = nullptr;
};

std::expected<Place, Error> resolve(const json& v, const Mode& mode, const Stations* stations, const Speeds& speeds,
                                    bool leaving, const char* what) {
    Place p;
    if (v.is_string()) {
        if (!stations || !(p.location = stations->find(v.get<std::string>())))
            return std::unexpected(Error{404, std::format("unknown location id {}", v.get<std::string>())});
        p.lat = p.location->lat, p.lon = p.location->lon;
        p.ends = Stations::ends(mode.touches[stations->index.at(p.location->id)], mode.graph, speeds, leaving);
        if (p.ends.empty())
            return std::unexpected(Error{422, std::format("{} {} is too far from the street graph", what, p.location->id)});
        return p;
    }
    if (!v.is_array() || v.size() != 2 || !v[0].is_number() || !v[1].is_number() || std::abs(v[0].get<double>()) > 90
        || std::abs(v[1].get<double>()) > 180)
        return std::unexpected(Error{400, std::format("{} must be [lat, lon] or a location id", what)});
    p.lat = v[0], p.lon = v[1];
    const auto access = mode.snap.nearest(p.lat, p.lon, p.snap_m);
    if (access.empty())
        return std::unexpected(Error{422, std::isinf(p.snap_m)
                                              ? std::format("{} is more than {} m from the street graph", what, mode.graph.max_snap_m)
                                              : std::format("{} is {:.0f} m from the street graph (max {} m)", what, p.snap_m, mode.graph.max_snap_m)});
    for (const auto& a : access) {
        const double wait = leaving ? mode.graph.entry_wait[a.node] : 0.0;
        p.ends.push_back({a.node, a.dist_m / speeds.walk + wait, a.dist_m, wait});
    }
    return p;
}

// The cheapest path between two places; totals, the path as [lon, lat], the elevators and steps on it.
std::expected<json, Error> route(const Mode& mode, Search& search, const Place& from, const Place& to, const Speeds& speeds) {
    const Graph& g = mode.graph;
    const auto hit = search.run(from.ends, speeds, to.ends);
    if (!hit) return std::unexpected(Error{404, "no path"});
    const auto& t = to.ends[*hit];
    const auto edges = search.path_to(t.node);
    const auto start = edges.empty() ? t.node : edges.front().first;
    json path = json::array({lonlat(from.lon, from.lat), lonlat(g, start)}), elevators = json::array(), steps = json::array();
    bool on_steps = false;
    for (const auto& [u, e] : edges) {
        path.push_back(lonlat(g, g.target[e]));
        if (g.flags[e] & kElevator) elevators.push_back(lonlat(g, u));  // where it is boarded
        if ((g.flags[e] & kSteps) && !on_steps) steps.push_back(lonlat(g, u));  // where a flight of steps starts
        on_steps = g.flags[e] & kSteps;
    }
    path.push_back(lonlat(to.lon, to.lat));
    json out{{"seconds", round_to(search.cost(t.node) + t.cost, 1)},
             {"walk_m", round_to(search.walk(t.node) + t.walk, 1)},
             {"bike_m", round_to(search.bike(t.node), 1)},
             {"wait_s", round_to(search.wait(t.node) + t.wait, 1)},
             {"snap_m", {round_to(from.snap_m, 1), round_to(to.snap_m, 1)}},
             {"path", path}, {"elevators", elevators}, {"steps", steps}};
    if (from.location) out["from_id"] = from.location->id;
    if (to.location) out["to_id"] = to.location->id;
    return out;
}

// Every location reachable within `limit` seconds from a place (direction "from"), or from which the place is
// reachable (direction "to", on the reversed graph). One search; metro transfers are relaxed once afterwards.
json access(const Mode& mode, Search& search, const Stations& stations, const Place& place, bool from,
            const Speeds& speeds, double limit) {
    search.run(place.ends, speeds, {}, limit);
    const auto n = stations.list.size();
    std::vector<double> best(n, kInf), walk(n), bike(n), wait(n);
    for (std::size_t i = 0; i < n; ++i) {
        for (const auto& e : Stations::ends(mode.touches[i], mode.graph, speeds, !from)) {
            if (!search.reached(e.node)) continue;
            if (const double c = search.cost(e.node) + e.cost; c <= limit && c < best[i])
                best[i] = c, walk[i] = search.walk(e.node) + e.walk, bike[i] = search.bike(e.node), wait[i] = search.wait(e.node) + e.wait;
        }
    }
    const double lift = stations.no_steps.contains(mode.name) ? stations.elevator_s : 0.0;
    for (std::size_t i = 0; i < n; ++i) {  // in-station transfers: one hop is enough (they are symmetric)
        if (best[i] == kInf) continue;
        for (const auto& [j, m] : stations.list[i].transfers)
            if (const double c = best[i] + m / speeds.walk + lift; c <= limit && c < best[j])
                best[j] = c, walk[j] = walk[i] + m, bike[j] = bike[i], wait[j] = wait[i] + lift;
    }
    std::vector<std::size_t> order;
    for (std::size_t i = 0; i < n; ++i) if (best[i] < kInf) order.push_back(i);
    std::ranges::sort(order, {}, [&](std::size_t i) { return best[i]; });
    json out = json::array();
    for (const auto i : order)
        out.push_back({{"id", stations.list[i].id}, {"seconds", round_to(best[i], 1)}, {"walk_m", round_to(walk[i], 1)},
                       {"bike_m", round_to(bike[i], 1)}, {"wait_s", round_to(wait[i], 1)}});
    return {{"stations", out}, {"direction", from ? "from" : "to"}, {"limit_s", limit}};
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

// Are the matrices in `dir` the ones for the loaded overlay and graphs? meta.json (written by preprocess_street.py)
// records the overlay hash and the size of each graph file the matrices were built from.
json matrices_status(const std::filesystem::path& dir, const Modes& modes, const Stations* stations) {
    std::ifstream in(dir / "meta.json");
    const auto meta = in ? json::parse(in, nullptr, false) : json();
    if (!meta.is_object() || !meta.contains("stations_hash")) return {{"status", "missing"}};
    std::string status = "ok";
    if (!stations || meta["stations_hash"] != stations->hash) status = "stale";
    for (const auto& [name, m] : modes) {
        if (!std::filesystem::exists(dir / (name + ".bin"))) return {{"status", "missing"}, {"mode", name}};
        const auto size = std::filesystem::file_size(dir / std::format("graph_{}.bin", name));
        if (!meta.contains("graphs") || !meta["graphs"].contains(name) || meta["graphs"][name].value("bytes", 0ULL) != size)
            status = "stale";
    }
    return {{"status", status}, {"stations_hash", stations ? stations->hash : ""},
            {"matrices_stations_hash", meta["stations_hash"]}, {"built", meta.value("built", "")}};
}

// POST /route {from, to, mode, speeds?}; POST /access {point, mode, direction, limit_s?, speeds?}; GET /health.
// from / to / point: [lat, lon] or a location id. Keys the router does not support yet are answered with 501.
void serve(const std::filesystem::path& dir, int port, unsigned threads) {
    Modes modes;
    for (const auto* name : {"walk", "bike", "accessible", "stroller"})
        if (const auto file = dir / std::format("graph_{}.bin", name); std::filesystem::exists(file))
            modes.emplace(name, std::make_unique<Mode>(name, file));
    if (modes.empty()) throw std::runtime_error("no graph_<mode>.bin in " + dir.string());
    std::optional<Stations> stations;
    if (const auto file = dir.parent_path() / "stations.json"; std::filesystem::exists(file)) stations = Stations::load(file);
    const Stations* st = stations ? &*stations : nullptr;
    if (st)
        for (auto& [name, m] : modes) m->touches = st->touches(name, m->snap);
    json health{{"modes", json::object()}};
    for (const auto& [name, m] : modes) health["modes"][name] = {{"nodes", m->graph.n}, {"edges", m->graph.m}};
    health["stations"] = st ? json{{"count", st->list.size()}, {"hash", st->hash}} : json();

    httplib::Server server;
    server.new_task_queue = [threads] { return new httplib::ThreadPool(threads); };
    auto reply = [](httplib::Response& res, int status, const json& body) {
        res.status = status;
        res.set_content(body.dump(), "application/json");
    };
    auto search_for = [](const Graph& g) -> Search& {  // one search buffer per worker thread and graph
        thread_local std::map<const Graph*, std::unique_ptr<Search>> searches;
        auto& s = searches[&g];
        if (!s) s = std::make_unique<Search>(g, true);
        return *s;
    };
    // Common request parsing: JSON object, only known keys (else 501), a loaded mode, optional speeds.
    auto parse = [&](const httplib::Request& req, httplib::Response& res, std::initializer_list<std::string_view> keys)
        -> std::optional<std::tuple<json, const Mode*, Speeds>> {
        const auto body = json::parse(req.body, nullptr, false);
        if (!body.is_object()) { reply(res, 400, {{"error", "the body must be a JSON object"}}); return std::nullopt; }
        json unimplemented = json::array();
        for (const auto& [key, value] : body.items())
            if (std::ranges::find(keys, std::string_view(key)) == keys.end()) unimplemented.push_back(key);
        if (const auto s = body.find("speeds"); s != body.end() && s->is_object())
            for (const auto& [key, value] : s->items())
                if (key != "walk" && key != "bike") unimplemented.push_back("speeds." + key);
        if (!unimplemented.empty()) {
            reply(res, 501, {{"error", "not implemented"}, {"unimplemented", unimplemented}});
            return std::nullopt;
        }
        const auto mode = modes.find(body.value("mode", std::string{}));
        if (mode == modes.end()) { reply(res, 400, {{"error", "mode must be one of the modes in /health"}}); return std::nullopt; }
        Speeds speeds = default_speeds(mode->second->graph);
        if (const auto s = body.find("speeds"); s != body.end()) {
            if (!s->is_object()) { reply(res, 400, {{"error", "speeds must be an object"}}); return std::nullopt; }
            speeds = {s->value("walk", speeds.walk), s->value("bike", speeds.bike)};
            if (!(speeds.walk > 0) || !(speeds.bike > 0)) { reply(res, 400, {{"error", "speeds must be > 0 (m/s)"}}); return std::nullopt; }
        }
        return std::tuple{body, mode->second.get(), speeds};
    };

    server.Get("/health", [&](const httplib::Request&, httplib::Response& res) {
        health["matrices"] = matrices_status(dir, modes, st);
        reply(res, 200, health);
    });
    server.Post("/route", [&](const httplib::Request& req, httplib::Response& res) {
        const auto parsed = parse(req, res, {"from", "to", "mode", "speeds"});
        if (!parsed) return;
        const auto& [body, mode, speeds] = *parsed;
        const auto from = resolve(body.value("from", json()), *mode, st, speeds, true, "from");
        const auto to = resolve(body.value("to", json()), *mode, st, speeds, false, "to");
        if (!from) return reply(res, from.error().status, {{"error", from.error().message}});
        if (!to) return reply(res, to.error().status, {{"error", to.error().message}});
        const auto out = route(*mode, search_for(mode->graph), *from, *to, speeds);
        out ? reply(res, 200, *out) : reply(res, out.error().status, {{"error", out.error().message}});
    });
    server.Post("/access", [&](const httplib::Request& req, httplib::Response& res) {
        const auto parsed = parse(req, res, {"point", "mode", "direction", "limit_s", "speeds"});
        if (!parsed) return;
        const auto& [body, mode, speeds] = *parsed;
        if (!st) return reply(res, 503, {{"error", "no stations.json loaded"}});
        const auto direction = body.value("direction", std::string("from"));
        if (direction != "from" && direction != "to") return reply(res, 400, {{"error", "direction must be from or to"}});
        const double limit = body.value("limit_s", 900.0);
        if (!(limit > 0)) return reply(res, 400, {{"error", "limit_s must be > 0"}});
        const bool from = direction == "from";
        const auto place = resolve(body.value("point", json()), *mode, st, speeds, from, "point");
        if (!place) return reply(res, place.error().status, {{"error", place.error().message}});
        reply(res, 200, access(*mode, search_for(from ? mode->graph : mode->rev), *st, *place, from, speeds, limit));
    });
    std::println(stderr, "serving {} with {} stations on http://127.0.0.1:{} with {} threads", health["modes"].dump(),
                 st ? st->list.size() : 0, port, threads);
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
        const Mode mode("cli", args[1]);
        Search search(mode.graph, true);
        const auto speeds = default_speeds(mode.graph);
        const auto [lat1, lon1] = parse_point(args[2]);
        const auto [lat2, lon2] = parse_point(args[3]);
        const auto from = resolve(json::array({lat1, lon1}), mode, nullptr, speeds, true, "from");
        const auto to = resolve(json::array({lat2, lon2}), mode, nullptr, speeds, false, "to");
        if (!from || !to) {
            std::println("{}", json{{"error", (from ? to.error() : from.error()).message}}.dump());
            return 1;
        }
        const auto out = route(mode, search, *from, *to, speeds);
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
