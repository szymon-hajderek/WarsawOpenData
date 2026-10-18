// The timetable for RAPTOR (timetable.bin, TTB1, written by backend/preprocess_transit.py) and its view for one
// service day: the trips that run that day (plus the previous day's trips still running after midnight) grouped
// into route patterns = same route and the exact same ordered list of locations. Inside a pattern trips never
// overtake each other (a trip that would is put into a new pattern), so a binary search on one stop's departures
// finds the earliest trip that can be boarded there.
#pragma once

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <list>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

struct Timetable {
    struct Route {
        std::string id, line, mode;
    };
    std::string stations_hash;
    std::uint32_t locations = 0;
    std::vector<Route> routes;
    std::vector<std::vector<std::uint32_t>> services;  // sorted YYYYMMDD dates
    std::vector<std::uint32_t> trip_route, trip_service, trip_offset;
    std::vector<std::string> trip_id, headsign;
    std::vector<std::uint32_t> call_loc;
    std::vector<std::int32_t> call_arr, call_dep;

    [[nodiscard]] bool runs(std::uint32_t trip, std::uint32_t date) const {
        const auto& d = services[trip_service[trip]];
        return std::ranges::binary_search(d, date);
    }
};

namespace ttb {
inline std::string read_str(std::ifstream& in) {
    std::uint32_t n = 0;
    in.read(reinterpret_cast<char*>(&n), sizeof n);
    std::string s(n, '\0');
    in.read(s.data(), n);
    return s;
}
inline std::uint32_t read_u32(std::ifstream& in) {
    std::uint32_t v = 0;
    in.read(reinterpret_cast<char*>(&v), sizeof v);
    return v;
}
template <class T>
void read_vec(std::ifstream& in, std::vector<T>& v, std::size_t count) {
    v.resize(count);
    in.read(reinterpret_cast<char*>(v.data()), static_cast<std::streamsize>(count * sizeof(T)));
}
}  // namespace ttb

inline Timetable load_timetable(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    char magic[4]{};
    in.read(magic, sizeof magic);
    if (!in || std::string_view(magic, sizeof magic) != "TTB1") throw std::runtime_error("not a timetable file (TTB1): " + path.string());
    if (ttb::read_u32(in) != 1) throw std::runtime_error("unknown timetable version: " + path.string());
    Timetable t;
    t.stations_hash = ttb::read_str(in);
    t.locations = ttb::read_u32(in);
    t.routes.resize(ttb::read_u32(in));
    for (auto& r : t.routes) {
        r.id = ttb::read_str(in);
        r.line = ttb::read_str(in);
        r.mode = ttb::read_str(in);
    }
    t.services.resize(ttb::read_u32(in));
    for (auto& s : t.services) ttb::read_vec(in, s, ttb::read_u32(in));
    const auto trips = ttb::read_u32(in);
    ttb::read_vec(in, t.trip_route, trips);
    ttb::read_vec(in, t.trip_service, trips);
    ttb::read_vec(in, t.trip_offset, trips + 1);
    t.trip_id.resize(trips);
    t.headsign.resize(trips);
    for (std::uint32_t i = 0; i < trips; ++i) t.trip_id[i] = ttb::read_str(in), t.headsign[i] = ttb::read_str(in);
    const auto calls = ttb::read_u32(in);
    ttb::read_vec(in, t.call_loc, calls);
    ttb::read_vec(in, t.call_arr, calls);
    ttb::read_vec(in, t.call_dep, calls);
    if (!in) throw std::runtime_error("truncated timetable file: " + path.string());
    if (trips && t.trip_offset.back() != calls) throw std::runtime_error("bad trip offsets in " + path.string());
    for (const auto l : t.call_loc)
        if (l >= t.locations) throw std::runtime_error("call at an unknown location in " + path.string());
    return t;
}

// YYYYMMDD of the day before.
inline std::uint32_t previous_day(std::uint32_t date) {
    using namespace std::chrono;
    const year_month_day ymd{year(static_cast<int>(date / 10000)), month(date / 100 % 100), day(date % 100)};
    const year_month_day prev{sys_days(ymd) - days(1)};
    return static_cast<std::uint32_t>(static_cast<int>(prev.year()) * 10000 + static_cast<unsigned>(prev.month()) * 100
                                      + static_cast<unsigned>(prev.day()));
}

inline bool valid_date(std::uint32_t date) {
    using namespace std::chrono;
    return year_month_day{year(static_cast<int>(date / 10000)), month(date / 100 % 100), day(date % 100)}.ok();
}

constexpr std::int32_t kDay = 86400;

// One service day: patterns with their trips' times (seconds after midnight of that day; the previous day's trips
// are shifted by -24 h), and where each location occurs in which pattern.
struct DayView {
    struct Pattern {
        std::uint32_t route;
        std::vector<std::uint32_t> stops;   // location indexes, in order (a location can repeat: loops)
        std::vector<std::uint32_t> trips;   // timetable trip indexes, earliest first
        std::vector<std::int32_t> arr, dep; // [trip * stops.size() + i]
        [[nodiscard]] std::size_t size() const { return stops.size(); }
        [[nodiscard]] std::int32_t arrival(std::size_t t, std::size_t i) const { return arr[t * stops.size() + i]; }
        [[nodiscard]] std::int32_t departure(std::size_t t, std::size_t i) const { return dep[t * stops.size() + i]; }
        // The earliest trip (index into trips) leaving stop i at or after `ready`; trips.size() when none.
        [[nodiscard]] std::size_t next_trip(std::size_t i, double ready) const {
            std::size_t lo = 0, hi = trips.size();
            while (lo < hi) {
                const auto mid = (lo + hi) / 2;
                if (departure(mid, i) < ready) lo = mid + 1;
                else hi = mid;
            }
            return lo;
        }
    };
    std::uint32_t date = 0;
    std::vector<Pattern> patterns;
    std::vector<std::vector<std::pair<std::uint32_t, std::uint32_t>>> incidence;  // location -> (pattern, index)
    std::size_t trips = 0;
};

inline DayView build_day(const Timetable& tt, std::uint32_t date) {
    DayView v;
    v.date = date;
    const auto prev = previous_day(date);
    struct Run {
        std::uint32_t trip;
        std::int32_t shift;
    };
    // group key: route + location sequence
    std::unordered_map<std::string, std::vector<Run>> groups;
    std::vector<std::string> order;  // deterministic pattern order
    for (std::uint32_t t = 0; t + 1 < tt.trip_offset.size(); ++t) {
        const auto a = tt.trip_offset[t], b = tt.trip_offset[t + 1];
        std::int32_t shift;
        if (tt.runs(t, date)) shift = 0;
        else if (tt.runs(t, prev) && tt.call_dep[b - 1] > kDay) shift = -kDay;  // yesterday's trip after midnight
        else continue;
        std::string key(reinterpret_cast<const char*>(&tt.trip_route[t]), sizeof(std::uint32_t));
        key.append(reinterpret_cast<const char*>(&tt.call_loc[a]), (b - a) * sizeof(std::uint32_t));
        auto [it, fresh] = groups.try_emplace(std::move(key));
        if (fresh) order.push_back(it->first);
        it->second.push_back({t, shift});
    }
    v.incidence.resize(tt.locations);
    for (const auto& key : order) {
        auto& runs = groups.at(key);
        const auto t0 = runs.front().trip;
        const auto a0 = tt.trip_offset[t0], n = tt.trip_offset[t0 + 1] - a0;
        auto dep0 = [&](const Run& r) { return tt.call_dep[tt.trip_offset[r.trip]] + r.shift; };
        std::ranges::stable_sort(runs, {}, dep0);
        // FIFO split: a run goes into the first pattern whose last run it does not overtake anywhere
        std::vector<DayView::Pattern> parts;
        for (const auto& r : runs) {
            const auto a = tt.trip_offset[r.trip];
            DayView::Pattern* fit = nullptr;
            for (auto& p : parts) {
                const auto last = p.trips.size() - 1;
                bool ok = true;
                for (std::uint32_t i = 0; i < n && ok; ++i)
                    ok = tt.call_arr[a + i] + r.shift >= p.arrival(last, i) && tt.call_dep[a + i] + r.shift >= p.departure(last, i);
                if (ok) { fit = &p; break; }
            }
            if (!fit) {
                fit = &parts.emplace_back();
                fit->route = tt.trip_route[r.trip];
                fit->stops.assign(tt.call_loc.begin() + a0, tt.call_loc.begin() + a0 + n);
            }
            fit->trips.push_back(r.trip);
            for (std::uint32_t i = 0; i < n; ++i) {
                fit->arr.push_back(tt.call_arr[a + i] + r.shift);
                fit->dep.push_back(tt.call_dep[a + i] + r.shift);
            }
            ++v.trips;
        }
        for (auto& p : parts) {
            const auto id = static_cast<std::uint32_t>(v.patterns.size());
            for (std::uint32_t i = 0; i < p.stops.size(); ++i) v.incidence[p.stops[i]].emplace_back(id, i);
            v.patterns.push_back(std::move(p));
        }
    }
    return v;
}

// The last few service days, built on first use. Thread-safe; views are immutable once built.
class DayCache {
public:
    explicit DayCache(const Timetable& tt, std::size_t keep = 3) : tt_(tt), keep_(keep) {}
    std::shared_ptr<const DayView> get(std::uint32_t date) {
        std::lock_guard lock(mutex_);
        for (auto it = days_.begin(); it != days_.end(); ++it)
            if ((*it)->date == date) {
                days_.splice(days_.begin(), days_, it);
                return days_.front();
            }
        days_.push_front(std::make_shared<const DayView>(build_day(tt_, date)));
        if (days_.size() > keep_) days_.pop_back();
        return days_.front();
    }

private:
    const Timetable& tt_;
    std::size_t keep_;
    std::mutex mutex_;
    std::list<std::shared_ptr<const DayView>> days_;
};
