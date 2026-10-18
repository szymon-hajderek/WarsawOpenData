# AGENTS.md

This file contains instructions for the AI assistant (Claude) working in this repository.
It is the single source of truth. `CLAUDE.md` only imports this file.
Everything in this repo (files, commits, PRs) is written in English.

## Keep It Simple

- **Do not build overly complicated things.** This is a hackathon POC.
- Prefer the simplest solution that works. Add complexity only when it is really needed.

## Git Rules

- **Only Claude performs commits, pushes, and other git operations.**
  The user does not create commits or push manually — all git history operations
  (commit, push, merge, rebase, tag, etc.) are carried out by the AI assistant.
- **Always make sure the local copy is up to date before starting any work:**
  1. Run `git fetch origin`.
  2. Check that local `main` is not behind `origin/main` (`git status -sb`).
  3. If it is behind, run `git checkout main` and `git pull origin main`.
  4. Only then create a new branch from the updated `main`.
- Also check that the local copy is up to date before committing/pushing on an existing branch.
- **Claude resolves merge conflicts automatically — the user never resolves them manually.**
  This applies in particular to `AGENTS.md`: whenever it conflicts, Claude resolves it on its own,
  keeping the valid rules and knowledge from both sides and removing duplicates or stale entries.

## Pull Requests

- **Every change is introduced through a Pull Request.**
- Whenever we want to add something, we create a new branch and open a Pull Request.
- Nothing is committed directly to `main` — changes land on `main` only via a merged PR.
- PRs are created with the GitHub CLI (`gh pr create`) and need a short title and description.
- **Before every PR, update the "Environment setup (for agents)" section in `README.md`.**
  If the branch adds or changes a dependency, a tool, a command, an env variable or a data download,
  write the exact install steps there (e.g. `uv sync`, `npm install`). If nothing changed, leave it as is.
  A new agent must be able to build the full environment from that section alone.
- **Before every PR, check `data/API.md`** (the API reference). If the branch adds, removes or changes an
  endpoint, a parameter, an answer field or an error, update `data/API.md` in the same PR. If the API did not
  change, leave the file as is.

## API contract

- **`data/API.md` is the contract of the backend API.** Backend and frontend code must follow it:
  use only the endpoints, parameters and answer fields written there.
- To change the API, edit `data/API.md` first, then the code, in the same PR. Never let code and `data/API.md` differ.
- Before you call or add an endpoint, read `data/API.md`. Use real answers from a running server for the examples.

## Street routing and the route engine: report only

- **The street routing code and the route engine have their own maintainers. Do not change them.**
  - Street routing: `backend/sources/osm.py`, `algorithms/street_model.py`, `algorithms/street_graph.py`,
    `algorithms/test_street_model.py`, `algorithms/router/` and `backend/preprocess_street.py`.
  - Route engine: `backend/app/routing/` and `algorithms/plan_trip.py` (now only the Warsaw clock helpers).
- When you find a problem there (bug, slowdown, stale cache, wrong result), only report it:
  1. Open a GitHub issue (`gh issue create`) with the symptom, how to reproduce it, measurements,
     the cause if known and a suggested fix.
  2. Tell the user about the problem and give the issue link.
- Do not fix it, and do not work around it in other code, unless the user asks for it.

## Feature Branches

- **One feature, one branch.** Do not add a second feature onto a branch that already has another.
  Finish that branch or leave it, update `main`, then start a new branch for the next feature.
- **Before you create any new branch, run the `deep-planning` skill** (`.claude/skills/deep-planning/SKILL.md`).
  Plan the change with the user first. Create the branch only after the user approves the plan.
  If your tool cannot run skills, read that file and follow its steps.
- **Every feature branch adds its own file under `changes/`**, named after the branch with
  slashes replaced by dashes (e.g. branch `feature/add-map` -> `changes/feature-add-map.md`).
- That file briefly describes the changes made on the branch — a short list of the most
  important points is enough — and is kept up to date as work on the branch progresses.
- **Do not use a single shared `CHANGES.md`.** One file per branch means two branches never
  edit the same file, so these change notes never cause merge conflicts. See `changes/README.md`.

## Project Knowledge

> **Claude: keep this section up to date automatically.**
> Whenever you learn something new about the project (goal, decisions, data sources,
> structure, conventions, team preferences), add it here in the same PR as the related
> change — without waiting to be asked. Update often, keep entries short, and fix or
> remove anything that is no longer true. If there is no related PR, open a small PR
> just for the knowledge update.

### What is this project

- **Name:** WarsawOpenData — a hackathon project based on Warsaw open data.
- **Goal:** a route planner for Warsaw that uses Veturilo (city bikes) at every stage of a trip
  together with public transport, which is hard to do today. Further goals: create new city data
  automatically (anonymised), inclusivity (adjust the pace for walking / cycling / stroller),
  and later "own bike + public transport".
- **POC use case:** (1) start = user's location or typed, (2) destination, (3) get n connection
  options that use Veturilo at any stage.
- **Planned features:** Veturilo rental integration, anonymised data for the city, intermediate
  stops, search priorities (max transfers, excluded areas, preferred modes, safety / roadworks,
  scenic, calories), "Discover" tourist routes, own bike, e-scooters, travel profile.
- **Jury criteria (design for them):** inclusivity / accessibility / diversity, scalability to
  other cities, safety, privacy, evidence-based, technical correctness, business model.
- **Time frame:** 24h hackathon, so keep everything simple.
- **Status:** the frontend UI exists. `uv run uvicorn main:app` serves the data and
  `POST /api/routes`. The route engine (`backend/app/routing/real_engine.py`) builds options from the router's
  RAPTOR trips (`POST /plan`) and street paths; the old Python transit planner is removed. Street paths (walk, bike, accessible, stroller) come from
  the C++ street router (`algorithms/router/`), which the backend starts. The router also plans transit trips with
  RAPTOR (`POST /plan`), the only transit planner (503 while its timetable is not ready). There is no mock engine and no frontend mock any more.

### Tech stack

- Frontend: React + TypeScript + Vite
- Map: Leaflet + MapLibre GL (OpenFreeMap vector tiles, OpenStreetMap data)
- Backend: Python + FastAPI
- Database: SQLite for optional journey statistics (`db/journey_stats.sqlite`, git-ignored).
  Source datasets remain raw files in `data/`, parsed by Python modules into caches at server start.
  PostgreSQL + PostGIS for source datasets later if needed.
- Routing: a long-running **C++ engine** loads its graph at startup and keeps it in memory.
  Today the street router runs (`algorithms/router/`, binary `street_router`, see Backend notes): street paths
  and station access, and RAPTOR transit trips (`POST /plan`). The route engine plans transit with `/plan`
  (`backend/app/routing/real_engine.py`; no Python fallback). `/plan` uses the GTFS timetable only: live
  delays are **not** a router input (router owner's decision; they are a UI-only display, `POST /api/live/route-delays`).
  "From the vehicle": `/plan` from the next stops of its GTFS trip at the scheduled arrival. Python does not send the graph.
  (OpenTripPlanner was the earlier idea; the team chose a custom C++ engine instead.)
- Deployment: Docker (planned, not set up yet)

### Folder structure

- `frontend/` — React + TypeScript + Vite app
- `ui/` — UI feature work; `ui/concept-art/` holds concept graphics
- `artifacts/` — self-contained HTML pages (visualizations); rebuilt by scripts, one folder per topic with its own `templates/` (`artifacts/README.md`)
  (`delays/` with `tests/`, `bus-detection/`, `veturilo-siting/`; no loose pages in `artifacts/` itself)
- `backend/` — FastAPI app
- `algorithms/` — algorithms (mandatory folder): pure functions + their pytest files (`nearest_buses.py`, `stop_order.py`);
  `algorithms/router/` the C++ street router, `algorithms/simulation/` the simulation scripts
- `integration/` — integration tests (simulation mode, scenarios); see `integration/README.md`
- `db/` — database files (`journey_stats.sqlite`, git-ignored)
- `routing/` — empty placeholder (was meant for OpenTripPlanner config)
- `data/` — datasets, one subfolder per data type: `gtfs/`, `gbfs/`, `osm/`, `geojson/`;
  `data/API.md` is the API reference (the contract), `data/REPORT.md` the data report

### Backend and data (`backend/`, `data/`)

- Python deps with **uv**: `cd backend && uv sync`. Run all commands from `backend/` (imports are flat:
  `config`, `sources.*`). uv picks Python 3.12 (`.venv` is git-ignored).
- One file per source in `backend/sources/` with `download()`, parse functions and a FastAPI `router`:
  `mkuran.py` (GTFS), `um_warszawa.py` (City Hall live APIs), `nextbike.py` (Veturilo GBFS), `osm.py`
  (walk / bike / accessible / stroller graph), `siting.py` (Warsaw boundary + Veturilo siting). `realtime.py`
  (trip-update / PLK delays) and `alerts.py` (ZTM alerts) only read live feeds. `sources/registry.py` lists every
  source, also the ones we only list.
- Commands: `uv run python download.py [source]`, `uv run uvicorn main:app --reload`
  (docs at `/docs`), `uv run python report.py` (writes `data/REPORT.md` + `data/report.json`).
- Raw data: GTFS zips and `warsaw_ztm.osm.pbf` are in Git LFS (`.gitattributes`); run `git lfs install`
  once after cloning. `data/derived/` holds parsed caches (git-ignored, built at server start, ~25 s
  for GTFS, ~17 s for OSM). The GTFS cache rebuilds by itself when `mkuran.CACHE_VERSION` changes;
  `osm_graph.npz` when the `.pbf` is newer (delete it after an OSM parser change); `stations.json` and the router's
  `street/graph_<mode>.bin` when their inputs are newer.
- GTFS geometry data: `mkuran.CACHE_VERSION` (version 2) marks metre distances and current boarding/platform
  fields. Old caches rebuild from existing ZIPs; mixed-feed maxima cannot detect truncated ZTM kilometres.
  Shapes follow `shape_pt_sequence`; `shape_slice` rejects unusable measures and `shape_by_stops` projects
  ordered calls onto source shape coordinates (e.g. WKD, which has no stop-to-shape distances).
- Dedup: stops only from GTFS. ZTM (bus, tram, metro) from `warsaw.zip` (its rail, route_type 2, is dropped:
  `DROP_ZTM_ROUTE_TYPES`), WKD from `wkd.zip`, all other trains incl. SKM from `polish_trains.zip`
  (`DROP_PKP_AGENCIES` is empty), only inside the ZTM bbox. Rail stations merge
  across feeds only rail-to-rail (same name, < 150 m, field `same_as`); never with bus / tram stops.
- IDs: global stop ids have a feed prefix (`ztm:700901`, `wkd:brzoz`, `pkp:33605_RAIL_1_5`).
  ZTM `700901` = zespół `7009` + słupek `01` = City Hall `busstopId` + `busstopNr`.
  Live `Lines` / `Brigade` = GTFS `route_short_name` / `block_short_name`.
  Veturilo and OSM have no shared ids: join by distance.
- City Hall APIs: `api.um.warszawa.pl` URLs need the trailing slash (`dbtimetable_get/`), else 301.
  The stop dictionary (`dbstore_get`) returns an error; GTFS covers it. The live vehicle feed
  also returns positions that are years old: filter by time (`max_age_s`).
- OSM map: `osm.download()` fetches Geofabrik `mazowieckie` (300 MB) once and `osm._clip()` keeps a 31 MB cut
  (`data/osm/warsaw_ztm.osm.pbf`): `BBOX` (ZTM area, 62 x 67 km) and only highway / crossing / railway /
  public_transport / entrance objects. 1.85 M nodes. Every stop / Veturilo station is < 100 m from the graph.
  (The older BBBike extract missed ~400 outer zone-2 stops.)
- Bus detection (`backend/bus_detect.py`): a thread polls live positions every 3 s (vehicle feed cache: 3 s; the feed itself changes about every 10 s) and keeps the last 3 positions per vehicle in memory.
  Without `PORTAL_KEY` the poller does not start and `GET /api/live/vehicles` returns 503 (no traceback).
  With the key it calls `fetch_vehicles` directly. `LIVE_BUSES_URL`, when set, is polled over HTTP instead.
  `POST /api/live/nearest-buses` ranks buses by MSE (m^2) between the user's 1-3 points and each bus track
  (each user point paired with the bus point closest in time), `algorithms/nearest_buses.py`. Returns 4
  (1 + 3 for the popup), no distance cut-off. Feed time is read as Europe/Warsaw (`clock.warsaw_epoch`).
- Tests: `cd backend && uv run pytest tests ../algorithms` (integration tests: `uv run pytest ../integration`) (`algorithms/` = pure functions, `backend/tests/` = API-level logic that needs no data files).
- Simulation (`algorithms/simulation/`): `record_buses.py` records 2 min of live buses (needs `PORTAL_KEY`) to
  `data/live/bus_track_sample.json` (committed); `simulate_nearest_buses.py` puts users on bus polylines with a GPS
  radius (10-100 m). Results in `algorithms/simulation/RESULTS.md`: own bus always in top-4, top-1 96-100% with
  3 points, 80-89% with 1 point.
- Second run (`artifacts/bus-detection/bus-detection-fraction.html`): point at u * L, u ~ U(0, 1), 10 points per line; same results.
  `rank_buses` is O(V*K*H + V log V), ~2 ms per request for ~880 buses.
- Visualization: `artifacts/bus-detection/bus-detection-simulation.html` (charts, one mini map per line, table), rebuilt with
  `uv run python ../algorithms/simulation/export_viz.py` (same seed, so the same numbers as RESULTS.md).
- Time zone: feed times and GTFS service midnights are Europe/Warsaw (`sim/clock.py`: `warsaw_epoch`,
  `warsaw_time`, `zoneinfo` + the `tzdata` package), whatever the server's zone. `record_buses.py` still stores
  vehicle `t` in the recorder's zone; `sim/scenario.py` undoes that with the poll time.
- Delay estimate (`algorithms/bus_delay.py`, `GET /api/live/delay?vehicle=bus-1234`): the poller also keeps a per-vehicle
  buffer (longest scheduled stop-to-stop time of the brigade's current trip + 60 s, else 10 min) with a midpoint between feed
  points (~5 s) unless a poll failed in between or the gap is > 25 s. The vehicle is projected on the GTFS shape of the trip with
  the same line + brigade (running now +- 15 min, < 100 m, timetable at that point closest to now; loops: the stretch nearest the last projection); last stop passed = K-1.
  Delay = time closest to K-1 within `DELAY_RADIUS_M` (default 30 m) - scheduled departure at K-1, shown at stop K; may be negative.
  Not found -> `available: false`. `shape_dist_traveled` in `warsaw.zip` is in km; `mkuran._shape_dist` converts
  it to metres. The cache version check rebuilds legacy truncated-kilometre data; `mkuran._trip_static`
  computes metres from coordinates independently. Tuning: `algorithms/simulation/tune_delay_radius.py`, results in `DELAY_RESULTS.md`.
  Delay simulation: `record_delay_sample.py` records all live vehicles + `/api/live/delay` answers from a local server into
  `data/live/delay_sample.json.gz` (t = seconds since local midnight of `date`); `simulate_delay.py` (`evaluate(sample, radius_m,
  drop, noise_m)`, for future R searches) compares the replayed estimate with the full-track reference (stop crossing on the shape);
  `export_delay_viz.py` builds `artifacts/delays/delay-statistics.html`. `search_delay_radius.py`: R 20..200 m every 10 m, then every 1 m
  between the two best neighbours; score = share of passes shown within 30 s. On the 2026-10-17 recording: 30 m 95.0%, best 80 m 96.5%
  (flat from 80 m); default still 30 m.
- Delays of suggested routes (`POST /api/live/route-delays`, `algorithms/route_delays.py`): a transit option id is
  `pt-<trip id>-<trip id>...` (built in `real_engine.py`; the endpoint depends on that format, the engine is not changed).
  Trip -> GTFS line + brigade -> live vehicle with the same Lines + Brigade -> the `/delay` estimate (`_delay_for`).
  Vehicle still on an earlier trip of its brigade: its current delay with `sameTrip: false`. `multi-N` options get nothing.
  Frontend: `useRouteDelays` (in `RouteOptionsSheet`, refresh 30 s) -> `LegChain` shows "· +3 min" / "punktualnie" /
  "2 min wcześniej" ("ok." when `sameTrip` is false) after the line; the engine's own "opóźnienie N min" tag is hidden then.
- Veturilo siting (`backend/sources/siting.py`, `algorithms/station_siting.py`, `GET /api/veturilo/siting`): Warsaw boundary
  (`data/geojson/warsaw.geojson`, Nominatim relation R336075) split into pointy-top axial hexes, radius 175 m (6476 hexes). Cost
  `J = -a*T*(1 + d*E) + b*P(d_net) + g*S`, `P = (1 - d/R)^2` below R; defaults a=1, b=1, g=0.5, d=0.5, R=1000 m (`DEFAULTS`).
  **T and E are mocks** (`data/mock/`, seed 20261017): T = mean of fake hourly counters per hex + IDW, normalised at p99; E = fake
  e-scooter crowding index 0..1 per 175 m hexagon (`scooter_intensity.json`): the city only receives this index per hexagon,
  never single scooter positions. E = mean of the index values whose hex centre falls in our hex, IDW for the rest.
  S = length-weighted mean of OSM segments (0 DDR/CPR, 0.3 quiet / painted lane,
  0.6 single-lane main, 1 multi-lane or trunk without a path). d_net = one multi-source Dijkstra on the bike graph in metres (up to
  5000 m), 0 in a hex with a station. Greedy top-N: after each pick, Dijkstra from the new station (limit R) and min.
  Not proposed: hexes with a station or without streets. Built in `warm()` (~2.5 min first time, cache `data/derived/siting_*.npz`).
  With these defaults T saturates at 1 in many hexes, so picks are mostly ranked by E and P; a weak quadratic P lets picks sit
  ~750 m (network) apart. Report: `uv run python siting_report.py` -> `data/SITING_REPORT.md`, `artifacts/veturilo-siting/veturilo-siting.html`
  (own canvas map with pan / zoom, no external scripts: Leaflet from a CDN failed to load for the user and broke the page).
- Feed without a key: mkuran GTFS-RT `vehicles.pb` refreshes about every 20 s; the City Hall feed is the main source.
- **Ride demo** (`./demo.sh [scenario]`): Demo tab in the frontend, shown only when `GET /api/sim/state` answers (backend in
  simulation mode). `POST /api/sim/ride` (`backend/sim/api.py`, `backend/sim/journey.py`) computes the whole ride (30-60 s), the page
  (`DemoPage.tsx`, `useRidePlayback`, `sim/ride.ts::sampleRide`) plays it back (pause, 1x / 10x / 60x, slider, GPS error). Route
  options for a free route are asked with `when` = simulated date + hour. `journey.py` lives in `backend/sim/`, not in `integration/`.
- **Integration tests** (`integration/`, see its README): `uv run pytest ../integration` from `backend/`, ~6 min.
  Simulation mode (`backend/sim/`): one clock (`sim.clock.now()`; live data code reads time there, never
  `time.time()` / `datetime.now()`; the route engine does not, so send `when`), a scenario file in `integration/scenarios/` replaces the vehicle feed
  (recorded or made from GTFS by `sim/synth.py`), Veturilo status and alerts. `SIM_SCENARIO=<name>` turns it on
  in the server and mounts `/api/sim/*`. Two kinds: `recorded/` and `gtfs/` (pytest markers). `ROUTE_ENGINE`
  (`app/routing/factory.py`) picks the engine; a new engine (C++) must pass this suite before it replaces `real`.
- **Do not change the route engine to make an integration test pass.** The engine (`backend/app/routing/`,
  `algorithms/plan_trip.py`) and the street routing code have their own maintainers. When a
  test finds an engine bug: open a GitHub issue (symptom, a `curl` to reproduce, measurements, cause if known), mark
  the case as strict xfail with the issue number, and tell the user. Simulation mode does not touch the engine either:
  tests send the simulated time as `when`.
- Engine bugs found so far: #63 (options leave hours after the query, night buses for 08:30), #64 (no option or no
  transit option at all), #65 (direct bus / tram options dropped after PR #56), #66 (`lateness.py` shows 4 min as 3).
- Walking-only route totals and arrival times come from the walking leg; never pass a zero-second total override
  to `_option`. Regression tests: `backend/tests/test_walk_duration.py` (including arrival after midnight; #72).
- The router returns 422 when a point is more than `MAX_SNAP_M` (1000 m, `osm.py`, stored in the graph file and
  checked by the C++ router) from the graph; `osm.nearest()` in Python has no limit.
- Street cost = length / speed + expected wait at crossings (HCM `(C-g)^2/2C`, constants `SPEED`,
  `WAIT` in `osm.py`). OSM has no signal timing tags in Warsaw. The wait is per edge (`osm.edges()`):
  signal nodes < 30 m apart by path form one junction (plus the nodes between them, e.g. islands),
  paid once (`algorithms/street_model.py`).
- A point (stop, address) joins the street graph through up to 6 nearest nodes (<= 30 m farther than the
  nearest; `osm.access`, `osm.points_graph` -> `StreetGraph`): virtual out / in nodes = multi-source Dijkstra with start
  costs. Access segments are walked (on a bike: pushed). The C++ router applies the same rule to any coordinate.
  Known gap: a pedestrian crosses a road only where OSM connects the two sidewalks (e.g. Wolica 01 / 02: 59 m apart, 695 m walk).
- ZTM posts in OSM: `public_transport=platform` nodes with `ref` = ZTM stop_id (`Grójecka 02` = `ref=435102`);
  90% of posts match, median 7 m from the GTFS point.
- Street modes (`osm.SPEED`): `walk`, `bike` (riding + pushing along the stroller graph where riding is not
  allowed), `accessible` (wheelchair: walk without steps, with `highway=elevator` ways; steps with
  `ramp:wheelchair=yes` count as step-free, plain `ramp=yes` does not), `stroller` (as accessible, plus steps with
  `ramp:stroller=yes`: narrow rails are not safe for a wheelchair, user decision). Every trip splits into `walk_m`
  (also a pushed bike, access, metro stairs), `bike_m` and `wait_s` (signals, crossings, 60 s per elevator in
  every mode); time = walk_m / walk speed + bike_m / bike speed + wait_s. Points join only the largest strongly connected component of the mode (`osm._mode_tree`):
  islands (1-2% of nodes) cannot reach anything, so no NaN pairs.
- Metro platforms (`ztm:7014M:P1`) join the graph through all GTFS entrances of their station
  (`location_type=2`, `7014M:E1..E9`): a 150 m walk; modes without steps (`osm.NO_STEPS`: bike, accessible,
  stroller) also take the elevator every entrance is assumed to have (+60 s).
  GTFS entrances match OSM `railway=subway_entrance` (251/253 within 30 m). GTFS `trips.txt` has
  `wheelchair_accessible` per trip (1 = yes for 96%).
- StationLocations (`backend/stations.py` → `data/derived/stations.json`, rules in `algorithms/station_map.py`): the one
  list of transport nodes for the router, backend (`GET /api/stations`) and frontend. GTFS = what exists and the
  fallback position; exact OSM match moves it (post `ref` = ZTM stop id ≤ 50 m: ~90%; rail platform number ≤ 50 m:
  160 / 207; metro entrances `subway_entrance` ≤ 30 m: 260 / 262). Veturilo unmapped. Ids = mkuran ids. Kinds:
  bus_post, tram_post, metro_platform (joins through all entrances, 150 m + elevator in no-steps modes, in-station
  transfer 200 m), rail_platform (`pkp:<station>_P<n>`, members = "N t. T" children), rail_station, veturilo.
  `hash` covers locations + model constants; the matrices record it in `meta.json`, `/health` says ok / stale / missing.
- Rail in mkuran: SKM now comes from `polish_trains.zip` (per platform), warsaw.zip route_type 2 is dropped
  (`DROP_ZTM_ROUTE_TYPES`). PKP platform children fold into `pkp:<station>_P<n>` (`platform` field), FALLBACK children
  into the station; `vertices()` = `boarding` locations; `canonical()` / `_targets()` know about platforms.
- Street router (C++, `algorithms/router/`, binary `street_router`): Python builds `graph_<mode>.bin` (SMG4) with
  the cost model (`osm.points_graph`, `preprocess_street.py --graph-only`); C++ does every street search.
  `street_router serve` (started by `main.py` via `backend/street_router.py`, port 8090, `ROUTER_URL` for an
  external one) answers `POST /route` {from, to, mode, speeds} between any coordinates (~1 ms nearby, ~0.4 s across
  the city); `from` / `to` may be station ids; `POST /access` = one Dijkstra from a point to every station within a
  time limit (or to the point: direction "to", reversed graph), the RAPTOR glue; `POST /plan` = RAPTOR (below);
  other keys get 501 "not implemented" (preferences come later). Router down = 503.
  The router returns **raw segment values only**: seconds, walk_m / bike_m / wait_s, path, elevators, steps, ids, and
  `legs` (one street leg; later whole trips in the same shape) with `segments` (ride / push / walk / steps /
  elevator / metro_access).
  `real_engine` builds every `RouteLeg` / `RouteOption` from them, plus GTFS and live data (issue #79: move
  `real_engine` to station ids, mapped positions and `fromId` / `toId` on legs).
  Target architecture (user): OSM layer for own bike / walk / accessible + a simple station network for RAPTOR with
  precomputed foot / bike paths; query = access Dijkstra → RAPTOR → egress Dijkstra.
  `street_router matrix` builds the stop-to-stop matrices (float32 (3, N, N): walk_m, bike_m, wait_s).
  `osm.route()` and `GET /api/osm/route` are gone; `real_engine._street()` calls the router. Full docs:
  `algorithms/router/README.md` (keep it current).
- RAPTOR in the router (`POST /plan`, design `docs/raptor-graph.md`, user's spec): `preprocess_transit.py` writes
  `data/derived/street/timetable.bin` (TTB1, `algorithms/timetable_file.py`; trips as calls at stations.json indexes,
  metro frequency runs expanded, rebuilt by `street_router.start()` when stale, ~10 s); C++ builds route patterns
  per service day (route + exact stop sequence, FIFO split, D−1 trips after midnight at −24 h; `transit.hpp`),
  footpaths = **dense matrix rows of the query's mode, no cut** (user decision; mmap, `matrix.hpp`), Veturilo = dock to
  dock from `bike.bin`, +1 leg, walk mode only, pickup 30 s / return 15 s, always available. Every limit unlimited by
  default (`max_legs`, `access_s`, `egress_s`, `footpath_s`, `veturilo_s`); `exclude_modes` skips transit modes / Veturilo.
  From the vehicle: `from` = next stop id, `time` = arrival there (same trip, `wait_s` 0). Backend relies on `/health`
  `timetable.status` and `plan.<mode>`: keep them stable. Answer = ids only (no positions, shapes,
  names): options `{seconds, dep_s, arr_s, transfers, walk_m, bike_m, wait_s, legs}`, transit legs with `trip_id`,
  `stops`, `wait_s`; format agreed with the router owner. A matrix is valid by size 3·N²·4 + `meta.json`
  `stations_hash` + `points.csv` ids (the per-mode `points` in `meta.json` can be stale: never read it).
  `real_engine._plan` calls `/plan` (#94): options through `legs_from_router`, title = lines joined by " + " ("Veturilo"),
  id `pt-<trips>` kept, one later query (+60 s) for more departures, dedupe, duration sort, max 6, excluded areas
  filtered after planning, the walk from `/route` when `/plan` gives no street-only trip. **No Python fallback** (user
  decision): `/health` `timetable.status` / `plan.<mode>` not "ok", or `/plan` 501 / 503 -> `POST /api/routes` 503
  `{"detail": "transit timetable not ready"}` (or the router's message); `/plan` 404 / 422 = no options. No live delay
  shift and no "opóźnienie" tag any more (`integration/gtfs/test_delay.py` is skipped). `lateness.py` and the planner
  functions of `plan_trip.py` were removed.
  Tests: `algorithms/test_raptor.py` (brute force on toy timetables), `backend/tests/test_plan_engine.py` (adapter).
- Rail platforms: `polish_trains.zip` has stations with children per platform + track (`33506_RAIL_2_20` =
  "2 t. 20"), also for SKM. They fold into one location per platform (`pkp:33506_P2`, see "Rail in mkuran");
  `GET /api/gtfs/stops` shows the children in `members`. Platform coordinates in GTFS look synthetic (evenly spaced);
  StationLocations moves a platform to the OSM `railway=platform` way where the number matches (160 / 207).

### Frontend (`frontend/`)

- Stack: React 18, Vite 5, TypeScript, Material UI v6 (+ icons), Leaflet 1.9 with `react-leaflet` 4.
  Vite 5 runs on Node 18.18+; stay on these versions (newer Vite needs Node 20+). On Node 26 (this Linux machine)
  `npm test` needs `NODE_OPTIONS=--no-experimental-webstorage`, else jsdom's `localStorage` is undefined.
- Screens, one flow: map with the user's location and start / destination fields on top ->
  list of connection options (with preview on the map) -> chosen route (clean route on the map,
  summary, steps). State lives in `src/App.tsx` (`step`: search / options / route, plus the active trip mode).
- **Routing seam.** `src/api/routes.ts` (`fetchRouteOptions`) calls the backend (`POST /api/routes`).
  If the backend is switched off (`VITE_API_URL=""`), unreachable or answers badly, the call throws `BackendOfflineError` and the app says "Nie połączono z serwerem".
  There is no in-browser mock (removed in `feature/no-mocks`): the app never shows made-up routes or vehicles. Types in `src/types.ts`.
- Backend URL: `src/config.ts` reads `VITE_API_URL` (default `http://localhost:8000`;
  `VITE_API_URL=""` in `frontend/.env` = backend off, the app says "Nie połączono z serwerem"). On a phone, `localhost` is the phone itself: set it to
  the page's own origin (`VITE_API_URL=https://<laptop-ip>:5173 npm run dev:https`); Vite then proxies `/api`.
- Place search: `src/api/geocode.ts` (`searchPlaces`, `MIN_QUERY`), debounced (300 ms), limited to Warsaw. Calls the backend (`GET /api/geocode`) when `API_URL` is set
  (from 2 characters; sends the user's position as `lat` / `lon`), else Nominatim directly (3 characters, ≈1 request/second limit). The backend answers with our own
  stops and Veturilo stations first (`algorithms/place_search.py`: start-of-word match, accents folded, distance as a tie-break), then Nominatim; stops still come when Nominatim is down.
  Without the backend the same search runs in the browser on `src/data/places.json` (about 3300 stop names and stations, 130 KB, a separate chunk loaded on first use;
  `src/utils/placeSearch.ts` is the TypeScript twin of `place_search.py`). Regenerate the file after a timetable or station change: `cd backend && uv run python export_places.py`.
- Colours: one palette, the Warsaw colours (red + yellow): `src/map/palette.ts` (`PALETTE`, light / dark). Red is the main
  colour in light mode, yellow the accent at night. It sets the map colours, the round map buttons / markers AND the accent
  of the whole UI (the MUI theme in `src/theme.ts` is built from it). The old lavender look and the look switch were removed.
  Colours and icons of transport modes: `src/modes.tsx`.
- Map: flat vector map, OpenFreeMap tiles (no key) drawn by MapLibre GL inside Leaflet (`@maplibre/maplibre-gl-leaflet`, loaded
  on demand). The style is ours: `src/map/mapStyle.ts` (colours from the palette, more labels when zoomed in). Map controls,
  markers and route in `src/components/MapView.tsx`. The old OSM raster map was removed. CARTO basemaps return
  "API KEY REQUIRED", so do not use them. OpenFreeMap has no SLA; there is no fallback.
- Two map looks: "flat" (default) and "liquid glass" (`createGlassStyle` in `src/map/mapStyle.ts`, colours `GLASS` in `src/map/palette.ts`, same red + yellow, light and dark).
  A layers button on the map switches them (`src/map/mapLook.ts`, `useMapLook`, localStorage `map-look`). Glass = glowing blurred roads, glass building tiles with a
  bright edge and a soft red shadow (`fill-translate`, no 3D: the Leaflet + MapLibre layer cannot tilt), light shores on water. Round buttons and markers get frosted glass
  (`src/map/glass.ts`, `backdrop-filter`); `src/map/glass.css` has the slowly drifting light over the map (`.glass-sheen`) and the pulse of the "me" / destination markers
  (both off with `prefers-reduced-motion`), plus bright sweeping bands, twinkling glints, a light running around the rim of round glass (`.glass-rim`) and a breathing glow of the road / shore layers (`VectorBasemap` animates `line-opacity`). Cards, sheets and the rest of the UI are not glass. Labels are shared (`labelLayers`).
- Corner radii: use the `RADIUS` tokens from `src/layout.ts` (sheet 28 px, card 20, tile / row / input 16, control 12,
  pill 999). **Pitfall:** in MUI `sx` a numeric `borderRadius` is multiplied by `theme.shape.borderRadius` (12), so
  `borderRadius: 4` is 48 px and swallows the content. Nested corners: inner radius = outer radius - padding.
- The line in the search card (start -> destination) is a gradient from `routeStart` to `routeEnd` of the palette.
- Draggable sheets: `src/components/SnapSheet.tsx` is the shared panel (floating above the bottom bar) that follows the finger and settles on 3 heights
  (`SheetSnap`: `bar` 76 px, `middle`, `full` = 62% of the screen / screen minus 200 px when wide; a quick flick skips a level, a tap steps up and from full back to
  the middle, Enter / arrow keys work too). Props: `header` (drag zone), `toolbar` and `footer` (pinned), scrolling `children`, per-sheet `middleHeight`; `useSnapHeights`
  gives the heights so `App.tsx` can keep the map visible above the sheet. Used by the vehicle popup (middle 258 px), the route list (352 px: header, filters, the selected
  route, pinned "Wybierz tę trasę") and the route details (292 px: start / destination, leg bar, time and distance; full = tiles, trip recorder, steps).
- "Which vehicle am I in?" window (`src/components/VehicleSheet.tsx`): shown on the start screen, starts in the middle (suggested vehicle + confirm), about 1/3 of the screen.
  Content below the visible height is `inert`. Shows the suggested vehicle (mode + line, direction and distance when known)
  and 3 others; "Inna linia" (autocomplete over all live lines) adds a hand-picked card; "Wykryj ponownie" (in the window)
  and the bus button on the map (start screen only, also brings the window back after "Nie jadę komunikacją") detect again;
  "Jadę tą linią" confirms. Data: `src/api/vehicle.ts` `detectVehicle` sends the user's last 1-3 positions (memory only,
  one every 10 s) to `POST /api/live/nearest-buses` and returns `{ candidates, lines }` (candidates carry `distanceM` =
  `rmse_m`, `vehicleNo`, `brigade`); when the backend is down it returns `offline: true` (the window says "Nie połączono z serwerem" with a retry button), with no location it returns nothing;
  an empty `API_URL` also counts as offline (no mock data).
  Delay: after "Jadę tą linią" `useVehicleDetection` starts `src/api/delay.ts` `watchDelay`, which polls `GET /api/live/delay` every 10 s and sends a `bus-delay`
  event on `window` (`BusDelayDetail` in `types.ts`); stops on a new detection or "Nie jadę komunikacją". No UI shows it yet.
  Detection runs once after start and on `requestLinePopup()`. Each detection also sends a `bus-popup` event on `window`
  (`{ candidates, lines, points }`). Direction is the GTFS `trip_headsign` for that line and brigade.
  The poller reads buses and trams. Concept: `ui/concept-art/current-line-popup.paint`.
- Navigation: bottom bar (`src/components/BottomNav.tsx`) with tabs Mapa and Preferencje; floating panels sit above it
  (`src/layout.ts`: `BOTTOM_NAV_HEIGHT`, `PANEL_BOTTOM`). The Preferences page is an overlay, the map stays mounted below.
- Trips with intermediate stops (up to 5, `MAX_STOPS` / `MAX_VIA`): `SearchCard.tsx` has "Dodaj przystanek", a drag handle on every row (⋮⋮, shown once there is at least one stop; start and destination too, so a stop can be exchanged with them: the rows `[start, ...stops, destination]` are reordered together;
  drag it up / down at any time, also after the row is filled in; ArrowUp / ArrowDown on the focused handle move it too; dragging while "Optymalna" is selected
  switches to "Moja kolejność") and a remove button per stop, and the chips "Moja kolejność" / "Optymalna"; the swap button reverses the whole trip. `fetchRouteOptions`
  takes `{ from, to, profile, via, order }` and sends `via` + `order` to `POST /api/routes`. Backend: `RouteRequest.via` / `order`, `RouteOption.waypoints`
  (start, stops in visiting order, destination), `RouteLeg.stop` (1-based number of the stop the leg ends at); `backend/app/routing/multi.py` asks the
  engine once per segment and chains the n-th best option of every segment (max 3 options); "optimal" = `algorithms/stop_order.py` (exact, a walk under 700 m otherwise a wait plus transit time,
  start and destination fixed). The next segment starts at the previous arrival plus 2 minutes.
- Preferences are sent with the search (`walkKmh`, `bikeKmh`, `stepFree`, `maxTransfers`, excluded areas, `excludeModes`, `body`). Only max walking time still filters the list in the browser. Model, level tables (default speeds), time
  rules and list filtering: `src/preferences/model.ts`; storage in localStorage key `preferences`
  (`src/preferences/PreferencesProvider.tsx`). Preferences page: `src/components/PreferencesPage.tsx`; reusable fields
  (levels + custom km/h, wheelchair, priorities, excluded districts / own points): `src/components/preferences/`.
  Time rules (`RuleDialog.tsx`) override any section for given days and hours (may cross midnight); the latest started
  active rule wins. `FilterSheet.tsx` = filters for the current search only (sorting, max transfers, vehicles, max walking
  time, step-free, pace / wheelchair, excluded areas, and "Zaawansowane" = all preferences as overrides). Max walking
  time still filters the list in the browser (`applyListFilters`); vehicles do not any more.
  "Środki transportu" (`Preferences.excludedModes`: bus / tram / metro / rail / veturilo, `TransportModesSection`, time rules may
  override it) is the persistent exclusion; the FilterSheet vehicle chips (`TripFilters.modes`, null = as in the preferences)
  replace it for one search. `routeSearchBody(trip, filters.modes)` turns both into `excludeModes` for `POST /api/routes`.
  `fetchRouteOptions` sends `walkKmh`, `bikeKmh`, `stepFree`, `maxTransfers`, excluded districts and points, `excludeModes` and `body`.
- Calories (device-side): `Preferences.body` (weight, height, age, sex; all optional, defaults 70 kg / 170 cm / 35 y) is edited in the "Kalorie" section of the
  Preferences page only (`components/preferences/BodySection.tsx`); rules and filters never override it (`applyOverrides` keeps it). `routeKcal(route, prefs)` in
  `src/preferences/model.ts` computes NET kcal of the walk / bike legs (MET from the Compendium of Physical Activities interpolated by the user's km/h x weight x hours
  minus resting energy (Mifflin-St Jeor); manual wheelchair uses a rough table from Conger and Bassett 2011, electric = 0; transit legs count as resting). The speed of a leg is its distance over its time
  (the pace from the preferences is the fallback). Routes carry no `calories` or `costPln` any more; kcal is worked out from the legs in the route list, details and the "most active"
  sort. `algorithms/calories.py` (`net_kcal`) is the same formula for any consumer of the route format. Not modelled yet: slope, carried load, bike type, wind.
- Route format (`data/API.md`): `RouteLeg.mode` is `walk`, `bike` (own bike), `veturilo` (rented), `bus`, `tram`, `metro`, `rail`; a leg also has
  `start` / `end` as `[lon, lat]` (the `path` stays `[lat, lng]`). `RouteOption` has `walkDistance` and `bikeDistance` (m) and no price: the backend's fare code
  (`algorithms/fares.py`) is not used by the route engine any more. Only "Najszybsza" is a backend tag; the frontend sort "Najaktywniejsze" uses `routeKcal`.
- Station-aware routing (#79): `real_engine` copies GTFS stops/calls onto `stations.locations()` positions and passes
  station IDs (including `vet:`) to the street router. One `legs_from_router` adapter converts paths/optional segments;
  all stop-touching legs carry `fromId` / `toId` and exact catalog `start` / `end` (street geometry stays router-rounded).
  Access/egress candidate ranking uses one `/access` call in the appropriate direction. Missing street paths
  drop mixed options; router downtime returns 503. `POST /api/routes` also accepts `travel` =
  walk / accessible / stroller / bike for street-only trips without timetable/live queries; default is transit.
  Stroller is a profile; stepFree/wheelchair uses the accessible graph. Route totals include pushed-bike metres
  in walkDistance and ridden metres in bikeDistance, including multi-stop trips.
- The C++ router never returns transit shapes. Transit geometry comes from GTFS in `real_engine` (`_ride_path`: `shape_slice`,
  then `shape_by_stops`); without any shape, a polyline through the stops with `approximatePath: true`.
- **Active trip** (`activeTrip` + `replanning` in `App.tsx`, `ActiveTripSheet.tsx`): "Rozpocznij przejazd" starts the recorder
  and enters the mode; "Zakończ" leaves it and saves the pace recording (recorder unchanged). The map follows the user
  (`MapView` `follow`). Progress = `src/utils/progress.ts` (`routeProgress`: projection on the leg paths, forward only;
  `nextStepText`: "Wysiadasz na: X", "Przesiadka: 175 z X", "Idź do: X"; > 150 m = "Zboczyłeś z trasy" + "Zmień trasę"),
  kept per route by `useTripProgress`. "W jakim pojeździe jestem?" opens `VehicleSheet` with the trip's own track
  (`tracker.track()` -> `detectionPoints`: last 3 recorder points >= 8 s apart). The confirmed vehicle lives in
  `useVehicleDetection` (independent of the destination; "Nie jadę komunikacją" clears it). "Zmień cel" / "Zmień trasę"
  open the full `SearchCard` ("← Wróć do przejazdu"); with a confirmed (not hand-picked) vehicle the start is
  `onboard:<vehicleId>` "Z pojazdu: 119 (następne przystanki)" and `POST /api/routes` gets `onboard: {vehicleId}`
  (timetable times only, no live delays in planning); 404 (`VehicleNotFoundError`) -> start = GPS position + a note.
  Choosing an option replaces the trip's route. A departure more than 1 min ahead (`src/utils/tripStart.ts`:
  `tripStartAt(departure, now, searchWhen?)`, `secondsUntil`, `mustWait`, `countdownText`) opens the trip in a waiting
  state ("Wyjazd o 14:30 · za 23 min", first step, "Anuluj" / "Ruszam teraz"): no progress, off-route or recording until
  the departure time (auto-start) or "Ruszam teraz"; `RouteDetailsSheet` `onStart(begin)` lets the app start the recorder
  later. The departure datetime = `tripStartAt(route.departure, now, departure)` with the picker's `when` (carried in
  `ActiveTrip.startAt`); "Zmień cel" inside a trip resets the picker to now. Tests: `src/activeTrip.test.tsx` (whole App, MapView mocked, recorded
  bus-1002 track from `data/live/bus_track_sample.json` in `src/test/busTrack.ts`, answers per data/API.md).
- Speed history (device-side, privacy first): in the route view "Rozpocznij przejazd" / "Zakończ" records GPS points (memory only, one every 4 s,
  Screen Wake Lock while recording) and sends the track once to `POST /api/history/records` (`backend/app/api/history.py`,
  `algorithms/speed_history.py::split_track`: shares the moving distance between the route's legs by planned distance, ignores standing
  still and GPS jumps, rejects implausible speeds, walking legs count as `walkAs` = walking or wheelchair). The response has no coordinates;
  the device keeps only these records in localStorage `trip-history` (`src/history/HistoryProvider.tsx`, max 200). The backend stores and logs nothing.
  `POST /api/history/summary` (`summarize`: moving speed = distance / moving time, latest 20 records per mode, outliers ignored, "enough" from 5 trips)
  gives the average per mode; the frontend falls back to `localSummary` when the backend is down. Preferences: each of Pieszo / Rower / Wózek shows
  "Twoja średnia z historii" with "Użyj X km/h" (when it differs by 10% or more) and the switch "Zawsze używaj średniej z historii" (`autoSpeed`; when on and
  enough trips, `applyHistory` in `src/preferences/model.ts` replaces the level / typed speed and the selector is locked). History can be cleared on the Preferences page.
- Departure time: the "Wyjazd: Teraz" chip in the search card (`DepartureControl.tsx`, helpers `src/utils/departure.ts`) picks
  Dziś / Jutro / a date + a time, or "Teraz". State `departure` in `App.tsx` (`null` = now, not saved). A chosen time is sent as
  `when` = `YYYY-MM-DDTHH:MM` with every search (transit, `via`, street-only); now sends no `when`. A past time is allowed (chip muted).
  The route list header shows "Wyjazd 14:30" when not now.
- Travel modes (`src/travel.ts`): chips in the search card (Komunikacja | Pieszo | Wózek inwalidzki | Wózek dziecięcy | Własny rower, not saved). `Komunikacja` is the
  normal `POST /api/routes` search. The other four are street-only trips: `src/api/streetRoute.ts` (`fetchStreetTrip`, also with `via` / `order`; `fetchStreetRoute` = no stops)
  posts to the same `POST /api/routes` with `travel` (`ROUTER_MODE`: `walk`, `accessible`, `stroller`, `bike`) and shows the one `RouteOption` of the answer as it is
  (checked by `isRouteOptions`; `GET /api/osm/route` is gone, the frontend no longer parses raw router answers). Errors are said in Polish: 422 "Punkt poza zasięgiem mapy",
  404 (or an empty list) "Brak trasy", 503 "Serwer tras nie działa", 400 "Ten tryb nie jest jeszcze dostępny na serwerze". **No mock and no straight line** for street trips:
  a wheelchair user must know the path was really checked. Filters and sorting do not apply to a street trip.
- Route representation extras (all optional): `RouteLeg.elevators` / `steps` (`[lat, lon]`, drawn as icons via `accessPoints` in `src/utils/overlay.ts`),
  `RouteLeg.waitS` (transit: seconds at the boarding stop), `RouteLeg.tripId` (GTFS, no UI), `RouteOption.waitS` (all standing time). Texts from `src/utils/format.ts`:
  `formatWait` "czekasz N min" in the route steps, `formatTotalWait` "w tym czekanie N min" next to the duration (list + details); nothing below 60 s.
- Stop overlay: `RouteLeg.fromId` / `toId` (ids of `GET /api/stations`, `null` for a place that is not a stop; both optional until the backend sends them, see backend issue #79).
  `src/api/stations.ts` (`fetchStation`, `fetchStations(bbox)`), `src/hooks/useRouteStations.ts` loads the stops a route names (by id, cached), `src/utils/overlay.ts` (`buildOverlay`)
  returns the markers, the leg paths with their ends moved onto the stops and the metro entrances. The map draws small stop markers, joins the legs at them, draws metro rides
  dashed and muted, shows the entrance where a walk goes down, and elevator / steps icons on street trips. Without answers the overlay is empty (nothing is made up).
- Backend calls build their URL with `apiUrl(path)` from `src/config.ts` (routes, geocode, history, vehicle, street routes,
  stations, journeys, sim); `src/api/delay.ts` still uses a relative `/api/live/delay`. An empty `API_URL` = backend off: routes and
  vehicles say "Nie połączono z serwerem"; only place search (Nominatim / `places.json`) and the local speed summary still work.
  Answers are checked in `src/api/validate.ts`; a wrong shape counts as "backend down".
- **A missing backend is said out loud.** An empty `API_URL`, a network error, a 5xx or a wrong shape means "not connected": a red snackbar "Nie połączono z serwerem. Sprawdź, czy backend działa."
  plus the same text in the route list (`useRouteSearch` `offline`) and the vehicle window (`useVehicleDetection` `offline`). A 4xx (the backend refused the query) stays the generic "Nie udało się pobrać tras".
- Hooks (`src/hooks/`): `useLocationTrack` (one `watchPosition` + the last 3 positions, cleaned up on unmount), `useRouteSearch`,
  `useVehicleDetection`, `useRouteStations`, `useRidePlayback` (demo). `App.tsx` only wires them. `ErrorBoundary` wraps the app. Selection and step are derived while rendering
  (no effects for derived state). Under the Preferences page the map and panels are `inert`.
- Selectable cards use `pressableProps` (`components/pressable.ts`): Enter / Space select, Space does not scroll. The map has ONE MapLibre
  layer; the light / dark switch calls `setStyle`. Leaflet marker icons are plain SVG from `ICON_PATH` in `modes.tsx` (no `react-dom/server`).
- Leg lines (`src/utils/legStyle.ts`, pure): a leg with `segments` is drawn per segment (`ride` solid, `push` dashed in the bike colour,
  `walk` dotted, `steps` / `elevator` / `metro_access` a short accent style), the stop connectors from `buildOverlay` stay on the first / last
  segment; without segments one line. A transit leg with `approximatePath: true` (#85) is dashed, details say "przebieg orientacyjny";
  a bike leg with segments shows "jazda X km, prowadzenie Y m".
- Checks: `npm run lint` (ESLint 8, `.eslintrc.cjs`), `npm test` (Vitest 1 + Testing Library, jsdom), `npm run build`.
- Vite proxies `/api` to the backend at http://localhost:8000.
- Geolocation works only on HTTPS or `localhost`. On a phone the plain `http://<laptop-ip>:5173` fails, so use `npm run dev:https` (vite `--mode https`, self-signed
  certificate from `@vitejs/plugin-basic-ssl`, accept the warning once). The app then shows a specific message (`geoErrorText`) when the page is not secure.
- Layout is mobile first; from 600 px (`sm`) the panels sit on the left side.
- Design references (user's screenshots): ride-choice list (selected card outlined), dark map with
  a clean route and round stop markers, light map with a bottom sheet.
- Run: `npm install`, `npm run dev` (http://localhost:5173), `npm run build` (type-check + build).

### Backend — routing API (`backend/app/`)

- Journey statistics (#52): `POST /api/journeys` records only the whole-trip start/destination of explicitly
  finished real GPS recordings after separate opt-in (off by default, localStorage `journey-statistics-enabled`).
  `backend/journey_stats.py` initializes SQLite and the local GTFS/GBFS anchor catalog at startup in both apps;
  optional `JOURNEY_STATS_DB` overrides `db/journey_stats.sqlite`. No cache builds or network calls in this request.
  Concrete object IDs and exact object coordinates are kept; current-location endpoints map to the geographically
  nearest boarding stop/platform or Veturilo station (no distance cutoff; ties by ID). Daily Warsaw-time counters,
  plus random per-recording token-only receipts for atomic retry deduplication; no full tracks, user/device IDs or
  precise journey timestamps. No public read/export endpoint. Counts and receipts stay until the DB is cleared.
  The recorder snapshots endpoints and opt-in at start; revocation invalidates the current submission.
  Interrupted and GPS-less recordings do not count; statistics failures do not block local speed history.
  Geocoded places use `osm:<node|way|relation>:<osm_id>` instead of Nominatim's temporary `place_id`.

- `app/routing/geometry.py` builds leg shapes for rendering: street path from the router, transit GTFS shape, else a
  polyline through the named points (`approximatePath`). The router answers ids only (null = query point);
  `legs_from_router()` accepts the old and the new router format. Legs carry `elevators` / `steps` (street),
  `waitS` + `tripId` (transit); `RouteOption.waitS` = all standing (transit waits + street waits).
- Separate package `backend/app/` holds the route models and `RealRouteEngine`. `backend/main.py`
  mounts it, so one uv process serves data, geocode and `POST /api/routes`.
- Models (`app/models.py`) mirror `frontend/src/types.ts` exactly (camelCase JSON keys; `from`
  via a Pydantic alias). FastAPI serializes responses by alias, so the output matches the UI types.
- Endpoints: `POST /api/routes` -> `RouteOption[]` (backend side of `fetchRouteOptions`),
  `GET /api/geocode?q=` -> `Place[]` (Nominatim proxy, Warsaw-limited), `GET /health` on `app.main`.
- Routing is behind a `RouteEngine` seam (`app/routing/engine.py`): `query_routes(...)` and
  `update_state(...)`. Current impl is `RealRouteEngine` (GTFS + OSM + Veturilo); the old
  `StubRouteEngine` mock was removed. A `CppRouteEngine` can replace the real engine later; nothing else changes.
- The street protocol is owned by the C++ team: `/route` returns `legs` with optional `segments`,
  while `/access` returns station costs without paths. Python preprocessing writes the graph files once;
  the long-running street router loads them and keeps them in memory. Python still plans GTFS combinations.
  A future C++ RAPTOR engine can return whole trips in the same leg shape. `update_state` remains unused;
  it is reserved for live data and derivatives, not graph uploads.
- Config via env vars (all optional): `CORS_ORIGINS`, `NOMINATIM_URL`, `NOMINATIM_USER_AGENT`.

### Decisions and notes

- Texts shown in the app are in Polish (users are in Warsaw); code, comments and docs are in English.
- The user is the UI person on the team; other people work on pathfinding, data and the backend.
- Local tooling quirks: `~/.npm` can be root-owned, so use `npm i --cache <some dir>`;
  `gh` is in `/opt/homebrew/bin` and `npm` in `/usr/local/bin` (add them to `PATH` in shell calls).
- In the Vite dev server, editing a file re-runs effects (hot reload), which resets the UI step.
- The browser pane has no geolocation, so the start must be typed when testing.

- **Users never call external APIs.** Only the app server does (City Hall, Nextbike, Nominatim, ...). The
  frontend talks to our backend, which caches the answers. Heavy work (cache builds) also runs on the server at
  start, never inside a user request.
- Backend robustness (see `config.py`): files are written atomically (`atomic_write`, `save_json`, `save_npz`),
  lazy builds sit behind a lock (`osm._LOCK`, `mkuran._BUILD_LOCK`), `TTLCache` is thread-safe and bounded.
  `main.py` turns `UpstreamError` / `httpx.HTTPError` into 502, `MissingKey` into 503, a missing data file into 404,
  `street_router.RouterUnavailable` into 503, and answers 503 for `NEEDS_CACHES` paths while `READY` is cleared
  (warm-up at start: `journey_stats.initialize()`, `mkuran.warm()`, `osm.warm()`, `siting.warm()`, `street_router.start()`).
- API keys live only in `.env`, which is git-ignored. Never commit `.env` or paste a key into a file, commit or chat.
- `ACCESS.md` lists the keys (`PORTAL_KEY`, `WAW_API_KEY`, `PLK_KEY`), how to get them and how to send them.
- Empty folders are kept in git with `.gitkeep`.
- Docker files (`docker-compose.yml`, `Dockerfile`) are not added yet.
- The user writes in Polish; replies to the user are in Polish, repo content is in English.
- The Cursor workspace root is the parent folder `hackathon`, and this repo lives in
  its subfolder `WarsawOpenData`. The repo's instruction file is `AGENTS.md`, because
  Cursor reads it (a plain `CLAUDE.md` may not be loaded).
- Change notes live in `changes/` (one file per branch), not in a single shared
  `CHANGES.md`, so parallel branches do not create merge conflicts in change notes.
- `README.md` has an "Environment setup (for agents)" section: how to install the full environment
  (keys, frontend with npm, backend with uv). It is updated in every PR that changes setup.
