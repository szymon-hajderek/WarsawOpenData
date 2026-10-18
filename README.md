# WarsawOpenData

Route planner for Warsaw. It combines Veturilo (city bikes) with public transport at every stage of a trip.
A 24-hour hackathon project built on Warsaw open data.

> **Status:** proof of concept. The backend downloads and parses the data, serves it through FastAPI and answers
> route searches from the GTFS timetable, live data and street paths of the C++ street router. Transit routing
> (RAPTOR) in C++ is the next step.

## Goal

1. The user sets a start (own location or typed) and a destination.
2. The app shows n connection options that use Veturilo at any stage.
3. The user picks one and sees the route on the map, with a summary and steps.

The project aims at inclusivity (walking, cycling and stroller pace), safety, privacy and scalability to other cities.

## Features

Done:

- Map UI in Polish: start / destination fields, list of options, route preview, route details.
- Route options from real data (`POST /api/routes`): GTFS departures, Veturilo, live delays and alerts; trips with
  up to 5 intermediate stops.
- Street-only trips on foot, by wheelchair, with a stroller or by own bike, from the C++ street router
  (`algorithms/router/`, `POST /api/routes` with `travel`).
- Two map looks (flat, liquid glass), light and dark mode.
- "Which vehicle am I in?" window: nearest live buses by MSE (`POST /api/live/nearest-buses`), delay estimate
  (`GET /api/live/delay`).
- Preferences and filters, calories, speed history from the user's own trips (stored on the device).
- Data download and parsers for GTFS, City Hall live APIs, Veturilo (GBFS) and the OSM street graph.
- FastAPI endpoints for every data source; simulation mode with integration tests and a ride demo.

Planned:

- **Transit routing in C++** (RAPTOR on top of the street router). Python then sends only live data and values derived from it.
- **Online route planning.** Change the route while the user travels.

## Tech stack

- Frontend: React + TypeScript + Vite, Material UI, Leaflet + MapLibre (OpenFreeMap tiles)
- Backend: Python + FastAPI (data layer managed with uv; routing API in `backend/app/` uses venv)
- Routing: C++ street router (`algorithms/router/`, runs today); transit routing in Python
  (`backend/app/routing/`), RAPTOR in C++ planned
- Database: SQLite for opt-in journey counters; source datasets remain raw files in `data/`

## Folder structure

- `frontend/` — React app
- `backend/` — FastAPI app, data download and parsers (see `backend/README.md`)
- `data/` — datasets, the API reference `data/API.md` and the data report `data/REPORT.md`
- `algorithms/` — pure algorithm functions with their tests, the C++ street router (`algorithms/router/`) and the
  simulation scripts (`algorithms/simulation/`)
- `integration/` — integration tests in simulation mode (see `integration/README.md`)
- `db/` — the SQLite journey statistics file (git-ignored); `routing/` — empty placeholder
- `ui/` — UI concept art
- `artifacts/` — HTML pages with results (open in a browser), e.g. the bus detection simulation
- `changes/` — one change note per branch

## Quick start

Full steps are in "Environment setup (for agents)" below. In short:

```bash
cd frontend && npm install && npm run dev          # http://localhost:5173
cd backend && uv sync && uv run uvicorn main:app --reload   # http://localhost:8000/docs
```

## Data

- [Warsaw city API portal](https://api.um.warszawa.pl/) — live vehicle positions and timetables
- GTFS from [mkuran.pl](https://mkuran.pl/gtfs/) — ZTM, WKD and other trains
- Veturilo stations and bikes (Nextbike GBFS)
- OpenStreetMap street graph (Geofabrik `mazowieckie`, cut to the ZTM area)

Details, ID links and graph sizes: `data/REPORT.md`.

## Environment setup (for agents)

Follow these steps to get a working environment. Run them from the repo root.
Keep this section current: every PR that adds a dependency or a tool updates it.

1. **Keys.** Copy `.env.example` to `.env` and fill in the keys. See `ACCESS.md`. Never commit `.env`.
2. **Frontend** (`frontend/`). Needs Node 18.18 or newer (Vite 5). On Node 26 `npm test` needs
   `NODE_OPTIONS=--no-experimental-webstorage npm test` (otherwise jsdom's `localStorage` is undefined).
   - `cd frontend && npm install` (if `~/.npm` is root-owned: `npm install --cache <some dir>`)
   - `npm run dev` starts the app at http://localhost:5173
   - On a phone (same Wi-Fi) the location button needs HTTPS: stop the other dev server and run
     `VITE_API_URL=https://<laptop-ip>:5173 npm run dev:https`, then open `https://<laptop-ip>:5173` and accept the
     self-signed certificate warning once. Vite proxies `/api` to the backend on port 8000; `VITE_API_URL` must be the
     page's own origin, because the default `http://localhost:8000` points at the phone itself.
   - `npm run build` type-checks and builds
   - `npm run lint` runs ESLint (react-hooks + jsx-a11y rules); `npm test` runs the Vitest tests (jsdom, no browser needed)
   - optional: `VITE_API_URL` in `frontend/.env` points the app at the routing API
     (default `http://localhost:8000`; set `VITE_API_URL=""` to use the in-browser example data; with a backend URL that does not answer, the app says "Nie połączono z serwerem")
3. **Data** (`data/`). GTFS zips and the OSM extract are stored with Git LFS.
   - install Git LFS once (`brew install git-lfs` or your package manager), then `git lfs install` and `git lfs pull`
   - or download fresh copies: `cd backend && uv run python download.py` (the OSM step fetches Geofabrik
     `mazowieckie` (300 MB) and keeps a 31 MB cut, `data/osm/warsaw_ztm.osm.pbf`)
4. **Backend** (`backend/`, Python + FastAPI, managed with [uv](https://docs.astral.sh/uv/)).
   - install uv: `brew install uv` (or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - `cd backend && uv sync` installs Python 3.12 and all dependencies (`osmium`, `scipy`, `fastapi`, `tzdata`, `gtfs-realtime-bindings` ...)
   - run every backend command from `backend/`
   - `uv run uvicorn main:app --reload` starts the API at http://localhost:8000 (docs at `/docs`).
     This one process serves the data, geocode and `POST /api/routes` (real GTFS + OSM + Veturilo).
   - `uv run python report.py` rebuilds `data/REPORT.md` (sources, ID links, graph sizes, endpoints)
   - the server builds the GTFS / OSM caches in `data/derived/` at start (~25 s / ~17 s on the first run, a minute or two
     with a ready cache). Until then `/api/gtfs`, `/api/osm` and `/api/routes` answer 503 (`Retry-After: 30`)
   - GTFS caches carry a format version (`mkuran.CACHE_VERSION`) in `gtfs_stop_times.npz`; an old cache rebuilds
     automatically from the existing ZIPs. The OSM cache `osm_graph.npz` rebuilds when the `.pbf` is newer.
   - **street router (C++)**: needs CMake 3.20+ and a C++23 compiler (GCC 14+ or Clang 19+); the first configure
     downloads cpp-httplib and nlohmann/json. Build once:
     `cmake -S ../algorithms/router -B ../algorithms/router/build -DCMAKE_BUILD_TYPE=Release &&
     cmake --build ../algorithms/router/build`. The backend then starts it by itself (port 8090; it writes
     `data/derived/street/graph_*.bin` first if needed, ~30 s; log: `data/derived/street/router.log`). Without it,
     walk / bike legs and `/api/stations/health` answer 503. Optional `.env`: `ROUTER_URL` (use a router that runs elsewhere), `ROUTER_PORT`.
   - the first start also builds `data/derived/stations.json` (transport nodes mapped to OSM, a few seconds;
     `uv run python stations.py` rebuilds it and prints the match report)
   - street matrices for every pair of stops (optional: the server does not read them yet):
     `uv run python preprocess_street.py` (four modes, ~18 min on 16 threads, ~2.7 GB). Details: `algorithms/router/README.md`
   - `uv run pytest tests ../algorithms` runs the tests (pytest is in the `dev` group, installed by `uv sync`)
   - `uv run pytest ../integration` runs the integration tests: synthetic trips on real data in simulation mode,
     about 6 minutes, no keys needed (`-m recorded` / `-m gtfs` for one kind). Results: `integration/RESULTS.md`.
     See `integration/README.md`
   - optional `SIM_SCENARIO=<name>` starts the server in simulation mode with `integration/scenarios/<name>.json`
     (simulated clock, replayed feeds, `/api/sim/*` endpoints, no `PORTAL_KEY` needed)
   - ride demo: `./demo.sh [scenario]` from the repo root starts the backend in simulation mode and the frontend
     (needs `npm install` and `uv sync` once); open http://localhost:5173 and use the "Demo" tab (it exists only in
     simulation mode). `API_PORT` changes the backend port
   - optional `ROUTE_ENGINE` picks the route engine: `real` (default) or `stub`
   - opt-in journey statistics: no extra dependency or database server is needed. Startup creates
     `db/journey_stats.sqlite` (git-ignored; SQLite from the Python standard library). The backend needs write
     access to `db/`. Optional `JOURNEY_STATS_DB` changes the file path; its parent is created automatically.
     Anchors load from local GTFS and `data/gbfs/veturilo_station_information.json`. To download the latter:
     `uv run python download.py nextbike`. Statistics return 503 if no anchor catalog or database is available.
     Enable **Statystyki podróży** in the app's Preferences (off by default), then explicitly start and finish
     a real GPS recording. `POST /api/journeys` stores exact selected object references and daily counts;
     current-location endpoints are replaced by the nearest transit/Veturilo anchor. No full GPS track,
     user/device identifier or precise journey timestamp is kept in this database. See `data/API.md`.
   - bus detection simulation: `uv run python ../algorithms/simulation/simulate_nearest_buses.py`
     (uses the committed sample; record a new one with `uv run python ../algorithms/simulation/record_buses.py`, needs `PORTAL_KEY`)
   - rebuild the results page `artifacts/bus-detection-simulation.html`: `uv run python ../algorithms/simulation/export_viz.py`
   - optional `.env` setting `LIVE_BUSES_URL`: where bus detection reads live bus positions (default: the City Hall feed via `PORTAL_KEY`). Without `PORTAL_KEY` the live-vehicle poller stays off and `GET /api/live/vehicles` returns 503.
   - Veturilo station siting (`GET /api/veturilo/siting`): the server builds the hex grid at start (first run ~2.5 min:
     one extra OSM pass, cached in `data/derived/siting_*.npz`). Trial report + map page:
     `uv run python siting_report.py` (writes `data/SITING_REPORT.md`, `data/siting_report.json`, `artifacts/veturilo-siting.html`;
     `--rebuild` recomputes the grid, `--mocks` regenerates the mock data in `data/mock/`). The Warsaw boundary
     `data/geojson/warsaw.geojson` is committed; `uv run python download.py siting` fetches it again from Nominatim
   - optional `.env` setting `DELAY_RADIUS_M`: radius for the delay estimate `GET /api/live/delay` (default `30`)
   - delay simulation on the committed recording `data/live/delay_sample.json.gz`: `uv run python ../algorithms/simulation/simulate_delay.py --radius 30`;
     rebuild the report `artifacts/delay-simulation.html`: `uv run python ../algorithms/simulation/export_delay_viz.py`;
     search the best radius (20-200 m every 10 m, then every 1 m): `uv run python ../algorithms/simulation/search_delay_radius.py`;
     record a new sample (server running, 30 min): `uv run python ../algorithms/simulation/record_delay_sample.py 30`
   - tune that radius on live data (needs `PORTAL_KEY`): `uv run python ../algorithms/simulation/tune_delay_radius.py 8`
5. **Routes** are part of the uv app in step 4. Do not start a second server on port 8000.
   The package `backend/app/` is the route engine imported by `main.py`. `requirements.txt` is only
   the old slim app and cannot load the timetable (it has no numpy/scipy).
6. **Database, Docker.** SQLite journey counters are initialized automatically (step 4).
   PostgreSQL + PostGIS and Docker are not set up yet.
