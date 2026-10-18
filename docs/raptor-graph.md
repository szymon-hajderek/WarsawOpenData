# Warsaw multimodal routing: graph and RAPTOR

The design of `POST /plan` in the C++ router (`algorithms/router/`). This file is the project state of the transit
planner: keep it in sync with the code. The API (body, answer, errors) is in `algorithms/router/README.md`
("`POST /plan`"); the backend API stays in `data/API.md`.

**Maintenance.** When a feed, an id mapping, the graph rules or the answer format changes, update this file,
`algorithms/router/README.md` and (for backend endpoints) `data/API.md` in the same change, and run the tests
(`cd backend && uv run pytest ../algorithms/test_raptor.py`). Keys never go into docs, code or generated files.

## 1. State and objective

- **Vertices** `P` = the StationLocations overlay (`data/derived/stations.json`, 7 542 locations): bus / tram posts,
  metro platforms, rail platforms, rail stations and Veturilo docks (`vet:<id>`). The matrix rows, the timetable and
  the answers all use these ids / indexes. Stop groups are metadata only (no free transfers inside a group).
- **Counted legs** `k`: boarding a bus / tram / metro / train = +1; renting a Veturilo bike and riding it from one dock
  to another = +1 (a second rental is another leg); walking (or riding one's own bike) = +0. `transfers = max(0, k − 1)`.
- `τ[k][p]` = earliest arrival at `p` with at most `k` counted legs. The answer is the Pareto set of
  `(k, arrival at the destination)` plus the street-only trip (`k = 0`), with predecessors for the itinerary.
- Times are seconds after midnight of the GTFS service day (Europe/Warsaw), also past 24:00.

## 2. The graph

1. **Vertices.** GTFS ZTM (`warsaw.zip`), WKD (`wkd.zip`) and the PKP / SKM / KM trains of `polish_trains.zip` in the
   ZTM area (mkuran): every stop_times stop is mapped by `mkuran.canonical()` to its overlay location (rail stations
   merged across feeds only rail-to-rail: same name, < 150 m; platform children fold into `pkp:<station>_P<n>`).
   Veturilo docks come from Nextbike GBFS.
2. **Route patterns** (`algorithms/router/transit.hpp`, built in C++ when a service day is first asked for): the trips
   that run on day D (from `calendar` / `calendar_dates`; frequency templates expanded into runs by
   `backend/preprocess_transit.py`) plus the trips of D − 1 still running after midnight (times −24 h), grouped by
   **route and the exact ordered location sequence** (a line number alone is not a pattern: one line has up to
   48 patterns). A trip that would overtake the previous trip of its pattern anywhere starts a new pattern, so a
   pattern's departures are sorted at every stop and `next_trip(pattern, i, t)` is a binary search
   (`O(log(D + 1))`). The real arrival / departure times of each trip are kept, never fixed segment weights.
   2026-10-21: 41 932 trips, 2 093 patterns, 49 723 stop occurrences.
3. **Route incidence.** For each location, every `(pattern, stop index)` occurrence; a loop that visits a location
   twice keeps both indexes.
4. **Footpaths `F`** from the all-pairs matrix of the query's mode (`data/derived/street/<mode>.bin`, float32
   `(3, N, N)` = walk_m, bike_m, wait_s from the OSM graph with the signal / crossing / elevator waits of
   `backend/sources/osm.py`). Seconds = `walk_m / v_walk + bike_m / v_bike + wait_s` with the query's speeds (the
   paths are optimal for the default speeds; the re-traced legs are exact). The matrix is a shortest-path closure, so
   a round takes at most one footpath; there is no chaining. **No cut by default**: the whole row of an improved
   stop is read (`footpath_s` limits it). Walking costs 0 legs. In `bike` mode the "footpaths" are rides of one's
   own bike (`bike.bin`), carried on transit.
5. **Veturilo `B`** (walk mode only): every ordered pair of docks; `arrival = t + pickup (30 s) + ride (bike.bin, the
   query's bike speed) + return (15 s)`, an `O(1)` lookup, no timetable. The walk to and from a dock is a footpath.
   Every dock is assumed to have a bike and a free place: live availability is not proof of future availability and
   is not used yet. `veturilo_s` limits the ride (default unlimited).
6. **First / last mile.** The origin and the destination are not vertices: one street Dijkstra from the origin to
   every location (`access_s`), one on the reversed graph from every location to the destination (`egress_s`), both
   unlimited by default (the whole graph, ~0.3 s each). A location id as origin / destination costs 0 there.
7. **Live data** (delays, docks) is not used yet. Plan: pushed from Python (`POST /delays {"trips": {trip_id:
   delay_s}}`), planned GTFS times stay the fallback; patterns are re-split if delays break the FIFO order.

### 2A. The matrix artifact

- Built offline by `backend/preprocess_street.py` (`street_router matrix`), one file per mode, rows / columns in
  `points.csv` order = `stations.json` order, `NaN` = no path, 0 on the diagonal, directed (one-way streets).
  `walk_m` / `bike_m` are the lengths of the time-optimal path.
- **Startup:** the router maps every `<mode>.bin` read-only once and keeps it for its lifetime (about 683 MB per
  mode, in the page cache); queries do constant-time lookups, never a Dijkstra between two stations. A mode refuses
  to plan (503, reason in `/health` → `plan`) when the file size is not `3 · N² · 4` with `N` = overlay size, when
  `meta.json` `stations_hash` differs from the overlay hash, or when the `points.csv` ids are not the overlay ids in
  order. The per-mode `points` fields of `meta.json` are not used (they can be stale).
- Rebuild the matrices when the overlay, the snapping, the OSM graph, the modes, speeds or wait rules change; a new
  GTFS timetable only needs `timetable.bin` (`preprocess_transit.py`, rebuilt automatically).

## 3. Query

Round `k = 1, 2, …` (until nothing improves or `k = max_legs`, default unlimited):

1. `τ[k] = τ[k − 1]`; `marked` = the locations improved in round `k − 1` (round 0 = the access search).
2. Collect the patterns through the marked locations with the smallest marked stop index each (deduplicated).
3. Scan each such pattern once, forward, from that index, with `active trip = none`: at stop `i`, if a trip is
   active, relax `τ[k][p_i]` with its arrival (predecessor: pattern, trip, boarding index, alighting index); then
   `candidate = next_trip(i, τ[k − 1][p_i])` and switch only when it is earlier than the active trip. Boarding always
   uses the previous round's labels.
4. Veturilo: from every dock marked in round `k − 1` to every other dock: `τ[k − 1][u] + pickup + ride + return`.
5. Footpaths from every location improved by 3 or 4, starting from that transit / Veturilo arrival (so a footpath
   never follows a footpath). The new `marked` = every location improved in round `k`, walking included.
6. Destination: `min_p τ[k][p] + egress[p]`. A journey with `k` legs is kept when it arrives **at least 1 s**
   earlier than every journey with fewer legs and than the street-only trip (float32 matrix entries and re-traced
   legs differ by milliseconds). Labels that cannot beat the best destination arrival so far are pruned.

**Itinerary.** Predecessors give the steps (access, rides, Veturilo, footpaths, egress); each street step is traced
again on the street graph with the query's speeds. The trip leaves "just in time": `dep_s` = first boarding minus
the street time before it; a transit leg's `wait_s` is the time standing at its stop.

**Invariant:** after round `k`, `τ[k][p]` is the earliest arrival at `p` with at most `k` counted legs under the
walking and Veturilo rules above; `τ[k − 1]` is never changed during round `k`.

## 4. Complexity

`N` = stop occurrences over all patterns of the day, `D` = most trips at one `(pattern, stop)`, `B` = dock pairs
(349² ≈ 122 k), `F` = footpath pairs read, `K` = rounds. A pattern is scanned once per round from a monotone index,
each occurrence does `O(1)` work and at most one binary search: `O(N log(D + 1))` per round, plus `O(B)` for
Veturilo and `O(F)` for footpaths, so `O(K · (N log(D + 1) + B + F))` per query. With no footpath cut a round reads
up to one dense row (7 542 entries) per improved location. Shared physical stops add no quadratic term: each
pattern visit is its own occurrence. Not included: the two street searches (access / egress), re-tracing the legs of
the answer, building a day's patterns (~0.5 s, cached for 3 days) and mapping the matrices at startup.

Measured (2026-10-18, real data, 4 server threads): ~0.7 s per query with the unlimited defaults, ~0.2 s with
15-minute access / egress / footpath limits.

## 5. Validation (`algorithms/test_raptor.py`)

- Against a brute-force search (every trip from every reached stop each round, every dock pair, footpaths from the
  improved stops) on 100 random toy timetables: shared stops, loops, overtaking trips, another service day, trips of
  the day before after midnight; Pareto sets with 0–3 legs.
- Named cases: an overtaking trip is found; yesterday's late trip and the service day; boarding fields, waits and
  `stops`; `null` ends with snap distances; Veturilo = +1 leg, only in walk mode, 30 / 15 s and their overrides;
  `max_legs`, `footpath_s`, query speeds, bike mode; errors (400 / 404 / 501), a timetable or matrix of another
  overlay or a truncated matrix → 503 for that mode only.
- Known gaps: GTFS pickup / drop-off restrictions are not kept (every call can be boarded and left), trip
  `wheelchair_accessible` is not used in accessible / stroller, no live data.

References: Delling, Pajor & Werneck, *Round-Based Public Transit Routing* (ALENEX 2012); GTFS Schedule Reference,
https://gtfs.org/documentation/schedule/reference/.
