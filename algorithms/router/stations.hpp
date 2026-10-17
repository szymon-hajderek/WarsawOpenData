// StationLocations: the transport-node overlay (data/derived/stations.json, built by backend/stations.py) and how a
// location joins a mode's street graph. A bus / tram post or a rail platform joins at its position; a metro platform
// joins through all entrances of its station (a fixed walk down, plus an elevator in modes without steps).
#pragma once

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>

#include "graph.hpp"
#include "search.hpp"
#include "snap.hpp"

struct Location {
    std::string id, kind;
    double lat, lon;
    std::vector<std::pair<double, double>> entrances;            // metro: street-level entrances (lat, lon)
    std::vector<std::pair<std::uint32_t, double>> transfers;     // metro: (other platform index, walk_m)
};

class Stations {
public:
    static Stations load(const std::filesystem::path& file) {
        std::ifstream in(file);
        if (!in) throw std::runtime_error("cannot read " + file.string());
        const auto doc = nlohmann::json::parse(in);
        Stations s;
        s.hash = doc.value("hash", "");
        const auto& c = doc.at("constants");
        s.metro_access_m = c.value("metro_access_m", 150.0);
        s.elevator_s = c.value("elevator_s", 60.0);
        for (const auto& m : c.value("no_steps", nlohmann::json::array({"bike", "accessible", "stroller"}))) s.no_steps.insert(m);
        for (const auto& l : doc.at("locations")) {
            Location loc{l.at("id"), l.at("kind"), l.at("position").at("lat"), l.at("position").at("lon"), {}, {}};
            for (const auto& e : l.value("entrances", nlohmann::json::array())) loc.entrances.emplace_back(e.at("lat"), e.at("lon"));
            s.index[loc.id] = static_cast<std::uint32_t>(s.list.size());
            s.list.push_back(std::move(loc));
        }
        for (const auto& l : doc.at("locations"))  // transfers refer to ids: resolve after all are known
            for (const auto& t : l.value("transfers", nlohmann::json::array()))
                if (const auto it = s.index.find(t.at("to")); it != s.index.end())
                    s.list[s.index.at(l.at("id"))].transfers.emplace_back(it->second, t.at("walk_m"));
        return s;
    }

    [[nodiscard]] const Location* find(std::string_view id) const {
        const auto it = index.find(std::string(id));
        return it == index.end() ? nullptr : &list[it->second];
    }

    // Where a location touches a graph, independent of speeds: snapped node, metres walked, extra wait.
    struct Touch {
        std::uint32_t node;
        double walk_m, wait_s;
    };

    // The touches of every location on one mode's graph (computed once per mode at server start).
    [[nodiscard]] std::vector<std::vector<Touch>> touches(std::string_view mode, const Snapper& snap) const {
        std::vector<std::vector<Touch>> out(list.size());
        const double lift = no_steps.contains(std::string(mode)) ? elevator_s : 0.0;
        for (std::size_t i = 0; i < list.size(); ++i) {
            const auto& loc = list[i];
            auto add = [&](double lat, double lon, double walk, double wait) {
                double nearest = 0;
                for (const auto& a : snap.nearest(lat, lon, nearest)) out[i].push_back({a.node, a.dist_m + walk, wait});
            };
            if (loc.kind == "metro_platform")
                for (const auto& [lat, lon] : loc.entrances) add(lat, lon, metro_access_m, lift);
            else
                add(loc.lat, loc.lon, 0.0, 0.0);
        }
        return out;
    }

    // The ends through which a location joins the graph, for the query's speeds. `leaving` = the location is the
    // start (the graph is entered: the node's entry wait is paid); otherwise it is the end. Empty = too far.
    static std::vector<End> ends(const std::vector<Touch>& touch, const Graph& g, const Speeds& speeds, bool leaving) {
        std::vector<End> out;
        for (const auto& t : touch) {
            const double wait = t.wait_s + (leaving ? g.entry_wait[t.node] : 0.0);
            out.push_back({t.node, t.walk_m / speeds.walk + wait, t.walk_m, wait});
        }
        return out;
    }

    std::vector<Location> list;
    std::unordered_map<std::string, std::uint32_t> index;
    std::string hash;
    double metro_access_m = 150, elevator_s = 60;
    std::set<std::string> no_steps;

};
