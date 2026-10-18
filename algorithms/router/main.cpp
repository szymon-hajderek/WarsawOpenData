// street_router: street paths for walk, bike, accessible and stroller, and transit trips (RAPTOR, POST /plan).
// README.md has the API and the file formats.
//   street_router matrix <graph.bin> <out.bin> [--threads N]     every pair of the graph's fixed points
//   street_router route <graph.bin> LAT,LON LAT,LON              one path, JSON on stdout
//   street_router serve <dir> [--port 8090] [--threads 4]        HTTP: POST /route, /access, /plan, /state, GET /health
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
#include <mutex>
#include <optional>
#include <print>
#include <set>
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
#include "matrix.hpp"
#include "raptor.hpp"
#include "transit.hpp"

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

// The cheapest path between two places: totals, the path as [lon, lat], its segments, the elevators and steps.
struct Trace {
    double seconds = 0, walk_m = 0, bike_m = 0, wait_s = 0;
    json path, segments, elevators, steps;
};

std::expected<Trace, Error> trace(const Mode& mode, Search& search, const Place& from, const Place& to, const Speeds& speeds) {
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
    // segments: consecutive parts of one kind (ride / push / walk / steps / elevator / metro_access), each with its
    // own path and metres; together they cover `path`. The ends (place -> graph) are walked, a bike is pushed there.
    const bool bike_mode = mode.name == "bike";
    const char* foot = bike_mode ? "push" : "walk";
    auto end_kind = [&](const Place& p) { return p.location && p.location->kind == "metro_platform" ? "metro_access" : foot; };
    json segments = json::array();
    auto add = [&](const char* kind, json a, json b, double metres) {
        if (!segments.empty() && segments.back()["kind"] == kind) {
            segments.back()["path"].push_back(std::move(b));
            segments.back()["length_m"] = segments.back()["length_m"].get<double>() + metres;
        } else {
            segments.push_back({{"kind", kind}, {"path", json::array({std::move(a), std::move(b)})}, {"length_m", metres}});
        }
    };
    add(end_kind(from), lonlat(from.lon, from.lat), lonlat(g, start), search.walk(start));
    for (const auto& [u, e] : edges) {
        const auto f = g.flags[e];
        const char* kind = (f & kElevator) ? "elevator" : (f & kMetro) ? "metro_access" : (f & kSteps) ? "steps"
                           : g.bike[e] > 0 ? "ride" : foot;
        add(kind, lonlat(g, u), lonlat(g, g.target[e]), g.walk[e] + g.bike[e]);
    }
    add(end_kind(to), lonlat(g, t.node), lonlat(to.lon, to.lat), t.walk);
    for (auto& seg : segments) seg["length_m"] = round_to(seg["length_m"].get<double>(), 1);
    return Trace{search.cost(t.node) + t.cost, search.walk(t.node) + t.walk, search.bike(t.node), search.wait(t.node) + t.wait,
                 std::move(path), std::move(segments), std::move(elevators), std::move(steps)};
}

// POST /route answer: the trace as top-level fields plus one leg.
std::expected<json, Error> route(const Mode& mode, Search& search, const Place& from, const Place& to, const Speeds& speeds) {
    auto tr = trace(mode, search, from, to, speeds);
    if (!tr) return std::unexpected(tr.error());
    auto& [seconds, walk_m, bike_m, wait_s, path, segments, elevators, steps] = *tr;
    const bool bike_mode = mode.name == "bike";
    auto end = [](const Place& p) {
        return json{{"id", p.location ? json(p.location->id) : json()}, {"lonlat", lonlat(p.lon, p.lat)}};
    };
    // legs: the user-visible parts of the trip (the format RAPTOR answers will use too); a street route is one leg
    json leg{{"mode", bike_mode ? "bike" : "walk"}, {"from", end(from)}, {"to", end(to)},
             {"seconds", round_to(seconds, 1)}, {"walk_m", round_to(walk_m, 1)}, {"bike_m", round_to(bike_m, 1)},
             {"wait_s", round_to(wait_s, 1)}, {"path", path}, {"segments", segments}};
    json out{{"seconds", round_to(seconds, 1)}, {"walk_m", round_to(walk_m, 1)}, {"bike_m", round_to(bike_m, 1)},
             {"wait_s", round_to(wait_s, 1)}, {"snap_m", {round_to(from.snap_m, 1), round_to(to.snap_m, 1)}},
             {"path", path}, {"elevators", elevators}, {"steps", steps}, {"legs", json::array({leg})}};
    if (from.location) out["from_id"] = from.location->id;
    if (to.location) out["to_id"] = to.location->id;
    return out;
}

// A street leg of a /plan answer: ids instead of positions (null = the query's own start / end, which then carries
// its snap distance), no names.
json street_leg(const char* leg_mode, const Trace& t, const Place& from, const Place& to) {
    auto id = [](const Place& p) { return p.location ? json(p.location->id) : json(); };
    json leg{{"mode", leg_mode}, {"from", id(from)}, {"to", id(to)}, {"seconds", round_to(t.seconds, 1)},
             {"walk_m", round_to(t.walk_m, 1)}, {"bike_m", round_to(t.bike_m, 1)}, {"wait_s", round_to(t.wait_s, 1)},
             {"path", t.path}, {"segments", t.segments}, {"elevators", t.elevators}, {"steps", t.steps}};
    if (!from.location) leg["from_snap_m"] = round_to(from.snap_m, 1);
    if (!to.location) leg["to_snap_m"] = round_to(to.snap_m, 1);
    return leg;
}

// Street times from a place to every location (direction "from"), or from every location to it ("to", on the
// reversed graph), within `limit` seconds; +inf = not reached. One search; metro transfers are relaxed afterwards.
struct Reach {
    std::vector<double> best, walk, bike, wait;
};

Reach reach(const Mode& mode, Search& search, const Stations& stations, const Place& place, bool from,
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
    return {std::move(best), std::move(walk), std::move(bike), std::move(wait)};
}

// POST /access answer: the reached locations, nearest first.
json access(const Mode& mode, Search& search, const Stations& stations, const Place& place, bool from,
            const Speeds& speeds, double limit) {
    const auto [best, walk, bike, wait] = reach(mode, search, stations, place, from, speeds, limit);
    const auto n = stations.list.size();
    std::vector<std::size_t> order;
    for (std::size_t i = 0; i < n; ++i) if (best[i] < kInf) order.push_back(i);
    std::ranges::sort(order, {}, [&](std::size_t i) { return best[i]; });
    json out = json::array();
    for (const auto i : order)
        out.push_back({{"id", stations.list[i].id}, {"seconds", round_to(best[i], 1)}, {"walk_m", round_to(walk[i], 1)},
                       {"bike_m", round_to(bike[i], 1)}, {"wait_s", round_to(wait[i], 1)}});
    return {{"stations", out}, {"direction", from ? "from" : "to"}, {"limit_s", limit}};
}

// One search buffer per worker thread and graph.
Search& search_for(const Graph& g) {
    thread_local std::map<const Graph*, std::unique_ptr<Search>> searches;
    auto& s = searches[&g];
    if (!s) s = std::make_unique<Search>(g, true);
    return *s;
}

// Live Veturilo availability, replaced as a whole by POST /state. A query copies the pointer once at its start, so
// one search sees one frozen state (RAPTOR needs it: availability must not depend on the arrival time, else being
// somewhere earlier would not always be better).
struct VeturiloState {
    std::vector<int> bikes;  // per location index: bikes available; -1 = no data (counts as 0 when min_bikes > 0)
    std::size_t docks = 0;   // docks with data
    std::chrono::system_clock::time_point updated;
};

class VeturiloStore {
public:
    [[nodiscard]] std::shared_ptr<const VeturiloState> get() const {
        std::scoped_lock lock(mutex_);
        return state_;
    }
    void set(std::shared_ptr<const VeturiloState> state) {
        std::scoped_lock lock(mutex_);
        state_ = std::move(state);
    }

private:
    mutable std::mutex mutex_;
    std::shared_ptr<const VeturiloState> state_;  // nullptr: no state received yet
};

// What POST /plan needs besides the street graphs: the timetable, its day views and the mapped matrices.
struct Transit {
    std::optional<Timetable> timetable;
    std::string timetable_error = "no timetable.bin";
    std::unique_ptr<DayCache> days;
    std::map<std::string, std::unique_ptr<Matrix>, std::less<>> matrices;
    std::vector<std::uint32_t> docks;  // Veturilo stations
    VeturiloStore veturilo;

    // "ok", or why the mode cannot plan.
    [[nodiscard]] std::string status(const std::string& mode) const {
        if (!timetable) return timetable_error;
        const auto m = matrices.find(mode);
        return m == matrices.end() ? "no stations.json" : m->second->ok() ? "ok" : m->second->error;
    }
};

// POST /state {"veturilo": {"vet:<id>": bikes, ...}}: the new availability of every dock (docks left out: no data).
std::expected<json, Error> set_state(const Stations& st, Transit& tr, const json& body) {
    const auto v = body.find("veturilo");
    if (v == body.end() || !v->is_object()) return std::unexpected(Error{400, "veturilo must be an object {id: bikes}"});
    auto state = std::make_shared<VeturiloState>();
    state->bikes.assign(st.list.size(), -1);
    json unknown = json::array();
    for (const auto& [id, bikes] : v->items()) {
        if (!bikes.is_number_integer() || bikes.get<long long>() < 0)
            return std::unexpected(Error{400, std::format("bikes of {} must be an integer >= 0", id)});
        const auto it = st.index.find(id);
        if (it == st.index.end() || st.list[it->second].kind != "veturilo") { unknown.push_back(id); continue; }
        state->bikes[it->second] = static_cast<int>(std::min<long long>(bikes.get<long long>(), 1 << 30));
        ++state->docks;
    }
    state->updated = std::chrono::system_clock::now();
    const auto docks = state->docks;
    tr.veturilo.set(std::move(state));
    return json{{"veturilo", {{"docks", docks}, {"unknown", unknown}}}};
}

json state_health(const Transit& tr) {
    const auto s = tr.veturilo.get();
    if (!s) return {{"veturilo", nullptr}};
    const std::chrono::duration<double> age = std::chrono::system_clock::now() - s->updated;
    return {{"veturilo", {{"docks", s->docks}, {"age_s", round_to(age.count(), 1)}}}};
}

// POST /plan: RAPTOR between two places on one service day. Answer: {"options": [{seconds, dep_s, arr_s, transfers,
// walk_m, bike_m, wait_s, legs}]}: the street-only trip and the Pareto set (counted legs, arrival). Legs name
// locations by id only (null = the query's own start / end); README.md has the leg fields.
std::expected<json, Error> plan(const Modes& modes, const Mode& mode, const Stations& st, Transit& tr, const json& body,
                                const Speeds& speeds) {
    const auto date_text = body.value("date", json()).is_string() ? body["date"].get<std::string>() : std::string();
    if (date_text.size() != 8 || !std::ranges::all_of(date_text, [](char c) { return c >= '0' && c <= '9'; })
        || !valid_date(static_cast<std::uint32_t>(std::stoul(date_text))))
        return std::unexpected(Error{400, "date must be YYYYMMDD"});
    const auto date = static_cast<std::uint32_t>(std::stoul(date_text));
    if (!body.contains("time") || !body["time"].is_number() || body["time"].get<double>() < 0 || body["time"].get<double>() > 2 * kDay)
        return std::unexpected(Error{400, "time must be seconds after midnight of the service day (0..172800)"});
    const double start = body["time"];
    double limits[6];
    const char* names[6] = {"access_s", "egress_s", "footpath_s", "veturilo_s", "veturilo_pickup_s", "veturilo_return_s"};
    const double defaults[6] = {kInf, kInf, kInf, kInf, 30, 15};
    for (int i = 0; i < 6; ++i) {
        const auto v = body.value(names[i], json(defaults[i]));
        if (!v.is_number() || v.get<double>() < 0) return std::unexpected(Error{400, std::format("{} must be a number >= 0", names[i])});
        limits[i] = v;
    }
    const auto max_legs = body.value("max_legs", json(std::numeric_limits<int>::max()));
    if (!max_legs.is_number_integer() || max_legs.get<long long>() < 0) return std::unexpected(Error{400, "max_legs must be an integer >= 0"});
    // min_bikes: rent only at docks with at least this many bikes in the state frozen at the start of this query
    const auto min_bikes = body.value("min_bikes", json(0));
    if (!min_bikes.is_number_integer() || min_bikes.get<long long>() < 0) return std::unexpected(Error{400, "min_bikes must be an integer >= 0"});
    const auto frozen = tr.veturilo.get();
    // exclude_modes: transit modes the search must not use ("bus" covers trolleybuses), and "veturilo"
    std::set<std::string, std::less<>> excluded;
    if (const auto ex = body.find("exclude_modes"); ex != body.end()) {
        static const std::set<std::string, std::less<>> allowed{"bus", "tram", "metro", "rail", "veturilo"};
        if (!ex->is_array()) return std::unexpected(Error{400, "exclude_modes must be a list"});
        for (const auto& m : *ex) {
            if (!m.is_string() || !allowed.contains(m.get<std::string>()))
                return std::unexpected(Error{400, "exclude_modes may only contain bus, tram, metro, rail, veturilo"});
            excluded.insert(m.get<std::string>());
        }
    }
    if (const auto s = tr.status(mode.name); s != "ok") return std::unexpected(Error{503, s});

    const auto from = resolve(body.value("from", json()), mode, &st, speeds, true, "from");
    if (!from) return std::unexpected(from.error());
    const auto to = resolve(body.value("to", json()), mode, &st, speeds, false, "to");
    if (!to) return std::unexpected(to.error());
    auto index = [&](const Place& p) { return p.location ? std::optional(st.index.at(p.location->id)) : std::nullopt; };
    const char* foot_mode = mode.name == "bike" ? "bike" : "walk";

    json options = json::array();
    auto add_option = [&](double dep, double arr, int legs_count, json legs) {
        double walk = 0, bike = 0, wait = 0;
        for (const auto& l : legs) walk += l.value("walk_m", 0.0), bike += l.value("bike_m", 0.0), wait += l.value("wait_s", 0.0);
        options.push_back({{"seconds", round_to(arr - dep, 1)}, {"dep_s", round_to(dep, 1)}, {"arr_s", round_to(arr, 1)},
                           {"transfers", std::max(0, legs_count - 1)}, {"walk_m", round_to(walk, 1)},
                           {"bike_m", round_to(bike, 1)}, {"wait_s", round_to(wait, 1)}, {"legs", std::move(legs)}});
    };
    // the street-only trip
    double best = kInf;
    if (const auto direct = trace(mode, search_for(mode.graph), *from, *to, speeds)) {
        best = start + direct->seconds;
        add_option(start, best, 0, json::array({street_leg(foot_mode, *direct, *from, *to)}));
    }
    if (max_legs.get<long long>() == 0) return json{{"options", options}};

    RaptorQuery q;
    const auto day = tr.days->get(date);
    q.day = day.get();
    q.foot = tr.matrices.at(mode.name).get();
    q.foot_speeds = speeds;
    q.access = reach(mode, search_for(mode.graph), st, *from, true, speeds, limits[0]).best;
    q.egress = reach(mode, search_for(mode.rev), st, *to, false, speeds, limits[1]).best;
    if (const auto i = index(*from)) q.access[*i] = 0;
    if (const auto i = index(*to)) q.egress[*i] = 0;
    q.start = start, q.initial_best = best;
    q.footpath_s = limits[2], q.veturilo_s = limits[3], q.pickup_s = limits[4], q.return_s = limits[5];
    if (!excluded.empty())
        for (const auto& r : tr.timetable->routes)
            q.skip_route.push_back(excluded.contains(r.mode == "trolleybus" ? std::string("bus") : r.mode));
    q.max_legs = static_cast<int>(std::min<long long>(max_legs.get<long long>(), std::numeric_limits<int>::max()));
    // Veturilo only on foot (walk mode): the dock-to-dock ride comes from the bike matrix
    const Mode* bike_mode = nullptr;
    Speeds bike_speeds = speeds;
    if (mode.name == "walk" && !excluded.contains("veturilo") && tr.status("bike") == "ok") {
        if (const auto b = modes.find("bike"); b != modes.end()) {
            bike_mode = b->second.get();
            const auto s = body.find("speeds");
            bike_speeds = {speeds.walk, s != body.end() && s->contains("bike") ? speeds.bike : bike_mode->graph.bike_speed};
            q.bike = tr.matrices.at("bike").get(), q.bike_speeds = bike_speeds, q.docks = tr.docks;
            for (const auto d : tr.docks)
                if (min_bikes.get<long long>() == 0 || (frozen && frozen->bikes[d] >= min_bikes.get<long long>())) q.pickup.push_back(d);
        }
    }
    Raptor raptor;
    const auto journeys = raptor.run(q);

    const auto& tt = *tr.timetable;
    auto place = [&](std::uint32_t loc, const Mode& m, const Speeds& s, bool leaving) {
        return resolve(json(st.list[loc].id), m, &st, s, leaving, "stop");
    };
    const double lift = st.no_steps.contains(mode.name) ? st.elevator_s : 0.0;
    for (const auto& j : journeys) {
        struct Item {
            json leg;
            bool transit = false;
            double dep = 0, arr = 0;
        };
        std::vector<Item> items;
        bool ok = true;
        auto street = [&](const Mode& m, const Speeds& s, const Place& a, const Place& b, const char* leg_mode) {
            const auto t = trace(m, search_for(m.graph), a, b, s);
            if (!t) { ok = false; return json(); }
            return street_leg(leg_mode, *t, a, b);
        };
        for (const auto& step : j.steps) {
            if (!ok) break;
            switch (step.kind) {
            case RaptorStep::Access:
                if (index(*from) == step.to) break;
                if (const auto b = place(step.to, mode, speeds, false)) items.push_back({street(mode, speeds, *from, *b, foot_mode)});
                else ok = false;
                break;
            case RaptorStep::Egress:
                if (index(*to) == step.from) break;
                if (const auto a = place(step.from, mode, speeds, true)) items.push_back({street(mode, speeds, *a, *to, foot_mode)});
                else ok = false;
                break;
            case RaptorStep::Foot: {
                const auto a = place(step.from, mode, speeds, true), b = place(step.to, mode, speeds, false);
                if (!a || !b) { ok = false; break; }
                auto leg = street(mode, speeds, *a, *b, foot_mode);
                // an in-station transfer (two metro platforms of one station) the matrix may have used instead
                for (const auto& [k, m] : st.list[step.from].transfers) {
                    const double c = m / speeds.walk + lift;
                    if (k != step.to || (ok && leg["seconds"].get<double>() <= c)) continue;
                    const auto& la = st.list[step.from];
                    const auto& lb = st.list[step.to];
                    const json path = json::array({lonlat(la.lon, la.lat), lonlat(lb.lon, lb.lat)});
                    leg = {{"mode", foot_mode}, {"from", la.id}, {"to", lb.id}, {"seconds", round_to(c, 1)},
                           {"walk_m", round_to(m, 1)}, {"bike_m", 0.0}, {"wait_s", lift}, {"path", path},
                           {"segments", json::array({{{"kind", "walk"}, {"path", path}, {"length_m", round_to(m, 1)}}})},
                           {"elevators", json::array()}, {"steps", json::array()}};
                    ok = true;  // a failed street trace is replaced by the transfer
                }
                items.push_back({std::move(leg)});
                break;
            }
            case RaptorStep::Veturilo: {
                const auto a = place(step.from, *bike_mode, bike_speeds, true), b = place(step.to, *bike_mode, bike_speeds, false);
                if (!a || !b) { ok = false; break; }
                auto leg = street(*bike_mode, bike_speeds, *a, *b, "veturilo");
                if (!ok) break;
                const double extra = q.pickup_s + q.return_s;
                leg["seconds"] = round_to(leg["seconds"].get<double>() + extra, 1);
                leg["wait_s"] = round_to(leg["wait_s"].get<double>() + extra, 1);
                leg["pickup_s"] = q.pickup_s, leg["return_s"] = q.return_s;
                leg["bikes"] = frozen && frozen->bikes[step.from] >= 0 ? json(frozen->bikes[step.from]) : json();
                items.push_back({std::move(leg)});
                break;
            }
            case RaptorStep::Transit: {
                const auto& P = day->patterns[step.pattern];
                const auto trip = P.trips[step.trip];
                const auto& route = tt.routes[P.route];
                json stops = json::array();
                for (auto i = step.board; i <= step.alight; ++i)
                    stops.push_back({{"id", st.list[P.stops[i]].id}, {"arr_s", P.arrival(step.trip, i)}, {"dep_s", P.departure(step.trip, i)}});
                const double dep = P.departure(step.trip, step.board), arr = P.arrival(step.trip, step.alight);
                items.push_back({json{{"mode", route.mode}, {"line", route.line}, {"route_id", route.id}, {"trip_id", tt.trip_id[trip]},
                                      {"headsign", tt.headsign[trip]}, {"from", st.list[step.from].id}, {"to", st.list[step.to].id},
                                      {"dep_s", dep}, {"arr_s", arr}, {"seconds", 0.0}, {"wait_s", 0.0}, {"stops", std::move(stops)}},
                                 true, dep, arr});
                break;
            }
            }
        }
        if (!ok) {
            std::println(stderr, "plan: a street leg of a {}-leg journey could not be traced; option dropped", j.legs);
            continue;
        }
        // leave home just in time for the first ride; a transit leg's wait_s = standing at its stop
        double dep = start, before = 0;
        for (const auto& it : items) {
            if (it.transit) { dep = it.dep - before; break; }
            before += it.leg["seconds"].get<double>();
        }
        double t = dep;
        json legs = json::array();
        for (auto& it : items) {
            if (it.transit) {
                const double wait = std::max(0.0, it.dep - t);
                it.leg["wait_s"] = round_to(wait, 1);
                it.leg["seconds"] = round_to(wait + it.arr - it.dep, 1);
                t = it.arr;
            } else {
                t += it.leg["seconds"].get<double>();
            }
            legs.push_back(std::move(it.leg));
        }
        add_option(dep, t, j.legs, std::move(legs));
    }
    return json{{"options", options}};
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

// POST /route {from, to, mode, speeds?}; POST /access {point, mode, direction, limit_s?, speeds?};
// POST /plan {from, to, mode, date, time, speeds?, limits?, min_bikes?}; POST /state {veturilo}; GET /health.
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
    // RAPTOR: the timetable (written by backend/preprocess_transit.py) and the matrices of every mode
    Transit transit;
    health["timetable"] = {{"status", "missing"}};
    if (const auto file = dir / "timetable.bin"; st && std::filesystem::exists(file)) {
        auto tt = load_timetable(file);
        if (tt.stations_hash != st->hash || tt.locations != st->list.size()) {
            transit.timetable_error = "timetable.bin was written for another stations.json";
            health["timetable"] = {{"status", "stale"}};
        } else {
            std::uint32_t first = 0, last = 0;
            for (const auto& d : tt.services)
                if (!d.empty()) first = first ? std::min(first, d.front()) : d.front(), last = std::max(last, d.back());
            health["timetable"] = {{"status", "ok"}, {"trips", tt.trip_id.size()}, {"routes", tt.routes.size()},
                                   {"first_date", std::to_string(first)}, {"last_date", std::to_string(last)}};
            transit.timetable = std::move(tt);
            transit.days = std::make_unique<DayCache>(*transit.timetable);
        }
    }
    if (st) {
        for (const auto& [name, m] : modes) {
            auto& mx = transit.matrices[name] = std::make_unique<Matrix>();
            mx->open(dir, name, *st);
        }
        for (std::uint32_t i = 0; i < st->list.size(); ++i)
            if (st->list[i].kind == "veturilo") transit.docks.push_back(i);
    }
    health["plan"] = json::object();
    for (const auto& [name, m] : modes) health["plan"][name] = transit.status(name);

    httplib::Server server;
    server.new_task_queue = [threads] { return new httplib::ThreadPool(threads); };
    auto reply = [](httplib::Response& res, int status, const json& body) {
        res.status = status;
        res.set_content(body.dump(), "application/json");
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
        health["state"] = state_health(transit);
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
    server.Post("/plan", [&](const httplib::Request& req, httplib::Response& res) {
        const auto parsed = parse(req, res, {"from", "to", "mode", "speeds", "date", "time", "max_legs", "access_s",
                                             "egress_s", "footpath_s", "veturilo_s", "veturilo_pickup_s",
                                             "veturilo_return_s", "exclude_modes", "min_bikes"});
        if (!parsed) return;
        const auto& [body, mode, speeds] = *parsed;
        if (!st) return reply(res, 503, {{"error", "no stations.json loaded"}});
        const auto out = plan(modes, *mode, *st, transit, body, speeds);
        out ? reply(res, 200, *out) : reply(res, out.error().status, {{"error", out.error().message}});
    });
    server.Post("/state", [&](const httplib::Request& req, httplib::Response& res) {
        const auto body = json::parse(req.body, nullptr, false);
        if (!body.is_object()) return reply(res, 400, {{"error", "the body must be a JSON object"}});
        json unimplemented = json::array();
        for (const auto& [key, value] : body.items())
            if (key != "veturilo") unimplemented.push_back(key);
        if (!unimplemented.empty()) return reply(res, 501, {{"error", "not implemented"}, {"unimplemented", unimplemented}});
        if (!st) return reply(res, 503, {{"error", "no stations.json loaded"}});
        const auto out = set_state(*st, transit, body);
        out ? reply(res, 200, *out) : reply(res, out.error().status, {{"error", out.error().message}});
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
