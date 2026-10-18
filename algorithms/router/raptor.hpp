// RAPTOR (Delling, Pajor, Werneck 2012) on one service day; docs/raptor-graph.md has the model and the proof.
// k counts boarded legs: a transit trip = +1, a Veturilo rental (dock to dock) = +1, walking = 0. Round k:
//   1. every pattern that serves a stop improved in round k-1 is scanned once, forward, from the first such stop;
//      boarding uses the labels of round k-1 (never ones improved in this round);
//   2. Veturilo: from every dock improved in round k-1 to every other dock (bike matrix + pickup + return);
//   3. footpaths from every location improved by 1 or 2, read from the mode's dense matrix row (one footpath per
//      round: the matrix is already a shortest-path closure).
// Labels that cannot beat the best arrival at the destination found so far are pruned.
#pragma once

#include <algorithm>
#include <cstdint>
#include <limits>
#include <vector>

#include "graph.hpp"
#include "matrix.hpp"
#include "transit.hpp"

struct RaptorQuery {
    const DayView* day = nullptr;
    const Matrix* foot = nullptr;  // footpaths: the mode's matrix
    Speeds foot_speeds{1.3, 4.2};
    const Matrix* bike = nullptr;  // Veturilo rides (nullptr: no Veturilo)
    Speeds bike_speeds{1.3, 4.2};
    std::vector<std::uint32_t> docks;  // locations that are Veturilo stations
    std::vector<double> access, egress;  // seconds from the start to each location / from each location to the end
    double start = 0;                    // departure time (s after midnight of the service day)
    double initial_best = kInfinity;     // arrival of the street-only trip: options must beat it
    double footpath_s = kInfinity, veturilo_s = kInfinity, pickup_s = 30, return_s = 15;
    int max_legs = std::numeric_limits<int>::max();
    static constexpr double kInfinity = std::numeric_limits<double>::infinity();
};

struct RaptorStep {
    enum Kind : std::uint8_t { Access, Transit, Veturilo, Foot, Egress } kind;
    std::uint32_t from = 0, to = 0;                             // locations
    std::uint32_t pattern = 0, trip = 0, board = 0, alight = 0;  // Transit: indexes into the day view
};

struct RaptorJourney {
    int legs = 0;  // counted legs
    double arrival = 0;
    std::vector<RaptorStep> steps;
};

class Raptor {
public:
    // A journey with more legs is kept only when it arrives at least this much earlier (float32 matrix entries and
    // re-traced street legs differ by milliseconds; such ties are not options).
    static constexpr double kMinGain = 1.0;

    // Pareto set (counted legs, arrival at the destination), fewest legs first; each at least kMinGain earlier than
    // every journey with fewer legs and than q.initial_best.
    std::vector<RaptorJourney> run(const RaptorQuery& q) {
        constexpr double inf = RaptorQuery::kInfinity;
        const auto& day = *q.day;
        const auto n = q.access.size();
        F_.assign(1, std::vector<Final>(n));
        T_.clear();
        std::vector<std::uint32_t> marked;
        std::vector<char> is_marked(n, 0), is_dock(n, 0);
        for (const auto d : q.docks) is_dock[d] = 1;
        for (std::uint32_t p = 0; p < n; ++p)
            if (q.access[p] < inf) F_[0][p] = {q.start + q.access[p], Final::Access, 0}, marked.push_back(p);
        double target = q.initial_best;
        std::vector<RaptorJourney> out;
        std::vector<std::int64_t> first(day.patterns.size(), -1);
        std::vector<std::uint32_t> queue, improved, next;
        std::vector<char> in_improved(n, 0);
        for (int k = 1; !marked.empty() && k <= q.max_legs; ++k) {
            for (const auto p : marked) is_marked[p] = 1;
            F_.push_back(F_.back());
            for (auto& f : F_.back()) f.kind = Final::None;  // inherited labels
            T_.emplace_back(n);
            auto& prev = F_[k - 1];
            auto& cur = F_[k];
            auto& tr = T_[k - 1];
            improved.clear();
            auto improve_t = [&](std::uint32_t p, const Trans& t) {
                tr[p] = t;
                cur[p] = {t.tau, Final::FromTrans, 0};
                if (!in_improved[p]) in_improved[p] = 1, improved.push_back(p);
            };
            // 1. patterns through the marked stops, each from its first marked stop
            queue.clear();
            for (const auto p : marked)
                for (const auto& [pat, i] : day.incidence[p]) {
                    if (first[pat] < 0) queue.push_back(pat), first[pat] = i;
                    else if (i < first[pat]) first[pat] = i;
                }
            for (const auto pat : queue) {
                const auto& P = day.patterns[pat];
                const auto none = P.trips.size();
                std::size_t trip = none, board = 0;
                for (auto i = static_cast<std::size_t>(first[pat]); i < P.size(); ++i) {
                    const auto p = P.stops[i];
                    if (trip != none) {
                        const double a = P.arrival(trip, i);
                        if (a < cur[p].tau && a < target)
                            improve_t(p, {a, Trans::Ride, pat, static_cast<std::uint32_t>(trip), static_cast<std::uint32_t>(board),
                                          static_cast<std::uint32_t>(i), 0});
                    }
                    if (prev[p].tau < inf) {
                        if (const auto c = P.next_trip(i, prev[p].tau); c < trip) trip = c, board = i;
                    }
                }
                first[pat] = -1;
            }
            // 2. Veturilo from the docks improved in the previous round
            if (q.bike)
                for (const auto u : q.docks) {
                    if (!is_marked[u]) continue;
                    for (const auto v : q.docks) {
                        if (v == u) continue;
                        const double ride = q.bike->seconds(u, v, q.bike_speeds);
                        if (!(ride <= q.veturilo_s)) continue;
                        const double a = prev[u].tau + q.pickup_s + ride + q.return_s;
                        if (a < cur[v].tau && a < target) improve_t(v, {a, Trans::Bike, 0, 0, 0, 0, u});
                    }
                }
            // 3. footpaths from the locations improved by 1 and 2
            next = improved;
            std::vector<char> in_next(in_improved);
            for (const auto p : improved) {
                const double base = tr[p].tau;
                const float* w = q.foot->walk(p);
                const float* b = q.foot->bike(p);
                const float* s = q.foot->wait(p);
                for (std::uint32_t j = 0; j < n; ++j) {
                    if (j == p || w[j] != w[j]) continue;  // self / NaN
                    const double c = w[j] / q.foot_speeds.walk + b[j] / q.foot_speeds.bike + s[j];
                    if (c > q.footpath_s) continue;
                    if (const double a = base + c; a < cur[j].tau && a < target) {
                        cur[j] = {a, Final::Foot, p};
                        if (!in_next[j]) in_next[j] = 1, next.push_back(j);
                    }
                }
            }
            for (const auto p : improved) in_improved[p] = 0;
            for (const auto p : marked) is_marked[p] = 0;
            // the destination
            std::int64_t best_p = -1;
            double arrival = target - kMinGain;
            for (const auto p : next)
                if (q.egress[p] < inf && cur[p].tau + q.egress[p] < arrival) arrival = cur[p].tau + q.egress[p], best_p = p;
            if (best_p >= 0) target = arrival;
            if (best_p >= 0) out.push_back(trace(k, static_cast<std::uint32_t>(best_p), target, q));
            marked.swap(next);
        }
        return out;
    }

private:
    struct Final {
        double tau = RaptorQuery::kInfinity;
        enum Kind : std::uint8_t { None, Access, FromTrans, Foot } kind = None;
        std::uint32_t from = 0;  // Foot: the location walked from (its transit label of the same round)
    };
    struct Trans {
        double tau = RaptorQuery::kInfinity;
        enum Kind : std::uint8_t { None, Ride, Bike } kind = None;
        std::uint32_t pattern = 0, trip = 0, board = 0, alight = 0, dock = 0;
    };

    RaptorJourney trace(int k, std::uint32_t p, double arrival, const RaptorQuery& q) const {
        RaptorJourney j{k, arrival, {}};
        j.steps.push_back({RaptorStep::Egress, p, p});
        int r = k;
        while (true) {
            while (r > 0 && F_[r][p].kind == Final::None) --r;
            const auto& f = F_[r][p];
            if (f.kind == Final::Access || r == 0) {
                j.steps.push_back({RaptorStep::Access, p, p});
                break;
            }
            if (f.kind == Final::Foot) {
                j.steps.push_back({RaptorStep::Foot, f.from, p});
                p = f.from;
            }
            const auto& t = T_[r - 1][p];
            if (t.kind == Trans::Ride) {
                const auto& P = q.day->patterns[t.pattern];
                j.steps.push_back({RaptorStep::Transit, P.stops[t.board], p, t.pattern, t.trip, t.board, t.alight});
                p = P.stops[t.board];
            } else {
                j.steps.push_back({RaptorStep::Veturilo, t.dock, p});
                p = t.dock;
            }
            --r;
        }
        std::ranges::reverse(j.steps);
        return j;
    }

    std::vector<std::vector<Final>> F_;  // F_[k][p]: best arrival at p with <= k legs
    std::vector<std::vector<Trans>> T_;  // T_[k-1][p]: the transit / Veturilo label of round k
};
