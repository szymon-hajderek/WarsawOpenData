# feature/cpp-router

Builds on `feature/street-time-split` (PR #59).

- The C++ street router (`algorithms/router/`, binary `street_router`) is the only street search:
  - `serve`: HTTP `POST /route` between any two coordinates for walk / bike / accessible; optional `speeds`
    (the path is optimal for them); any other option answers 501 "not implemented" so callers can relay options.
  - `route`: one path on the command line. `matrix`: the stop-to-stop matrices.
  - C++ joins coordinates to the graph itself (`snap.hpp`, the same rule as Python), and the search stops at the
    target. Code split into `graph.hpp`, `snap.hpp`, `search.hpp`, `main.cpp`; nlohmann/json added (CMake fetch).
- Graph file `SMG4`: no precomputed cost (C++ computes it from walk / bike / wait and the query speeds); default
  speeds, access rules, `usable` and `entry_wait` per node; coordinates as float64.
- `backend/street_router.py`: client + `start()` / `stop()`. `main.py` starts the router in the warm-up thread (writes
  stale graph files first) and stops it at shutdown; router down = 503.
- `osm.route()` removed; `/api/osm/route` and `real_engine._street()` call the router. `_street()` passes the
  profile's speeds and uses the accessible graph for the accessible profile.
- `osm.graph()` rebuilds `osm_graph.npz` when the `.pbf` is newer.
- `POST /api/routes` (Banacha -> Plac Unii): ~3 s instead of ~90 s.
