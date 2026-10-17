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
  `POST /api/routes`. The route engine (`backend/app/routing/real_engine.py`) builds options from
  GTFS departures, OSM walk/bike paths and live Veturilo docks. A C++ engine is still the later plan;
  `StubRouteEngine` remains only as the old mock.

### Tech stack

- Frontend: React + TypeScript + Vite
- Map: Leaflet + OpenStreetMap
- Backend: Python + FastAPI
- Database: none for now. Raw files in `data/`, parsed by Python modules on first use.
  PostgreSQL + PostGIS (or SQLite) later if needed.
- Routing: a long-running **C++ engine** keeps the graph + live state in memory; Python
  (FastAPI) is a thin backend that pushes updates and asks it for routes. (OpenTripPlanner
  was the earlier idea; the team chose a custom C++ engine instead.)
- Deployment: Docker

### Folder structure

- `frontend/` — React + TypeScript + Vite app
- `ui/` — UI feature work; `ui/concept-art/` holds concept graphics
- `artifacts/` — self-contained HTML pages (visualizations); rebuilt by scripts, templates in `artifacts/templates/`
- `backend/` — FastAPI app
- `algorithms/` — algorithms (mandatory folder): pure functions + their pytest files (`nearest_buses.py`, `stop_order.py`)
- `db/` — database files and setup
- `routing/` — OpenTripPlanner config
- `data/` — datasets, one subfolder per data type: `gtfs/`, `gbfs/`, `osm/`, `geojson/`;
  `data/API.md` is the API reference (the contract), `data/REPORT.md` the data report

### Backend and data (`backend/`, `data/`)

- Python deps with **uv**: `cd backend && uv sync`. Run all commands from `backend/` (imports are flat:
  `config`, `sources.*`). uv picks Python 3.12 (`.venv` is git-ignored).
- One file per source in `backend/sources/` with `download()`, parse functions and a FastAPI `router`:
  `mkuran.py` (GTFS), `um_warszawa.py` (City Hall live APIs), `nextbike.py` (Veturilo GBFS), `osm.py`
  (walk / bike graph). `sources/registry.py` lists every source, also the ones we only list.
- Commands: `uv run python download.py [source]`, `uv run uvicorn main:app --reload`
  (docs at `/docs`), `uv run python report.py` (writes `data/REPORT.md` + `data/report.json`).
- Raw data: GTFS zips and `Warsaw.osm.pbf` are in Git LFS (`.gitattributes`); run `git lfs install`
  once after cloning. `data/derived/` holds parsed caches (git-ignored, rebuilt on first use, ~25 s
  for GTFS, ~45 s for OSM).
- Dedup: stops only from GTFS. ZTM (bus, tram, metro, SKM) from `warsaw.zip`, WKD from `wkd.zip`,
  other trains from `polish_trains.zip` without SKM and only inside the ZTM bbox. Rail stations merge
  across feeds only rail-to-rail (same name, < 150 m, field `same_as`); never with bus / tram stops.
- IDs: global stop ids have a feed prefix (`ztm:700901`, `wkd:brzoz`, `pkp:33605_RAIL_1_5`).
  ZTM `700901` = zespół `7009` + słupek `01` = City Hall `busstopId` + `busstopNr`.
  Live `Lines` / `Brigade` = GTFS `route_short_name` / `block_short_name`.
  Veturilo and OSM have no shared ids: join by distance.
- City Hall APIs: `api.um.warszawa.pl` URLs need the trailing slash (`dbtimetable_get/`), else 301.
  The stop dictionary (`dbstore_get`) returns an error; GTFS covers it. The live vehicle feed
  also returns positions that are years old: filter by time (`max_age_s`).
- The BBBike OSM box (52.041-52.451 N, 20.653-21.408 E) is smaller than the ZTM area; ~400 outer
  stops snap far. Geofabrik `mazowieckie` + `osmium extract` is the fix if needed.
- Bus detection (`backend/bus_detect.py`): a thread polls `LIVE_BUSES_URL` (default our
  `/api/live/vehicles?type=bus`) every 3 s (vehicle feed cache: 3 s; the feed itself changes about every 10 s) and keeps the last 3 positions per vehicle in memory.
  `POST /api/live/nearest-buses` ranks buses by MSE (m^2) between the user's 1-3 points and each bus track
  (each user point paired with the bus point closest in time), `algorithms/nearest_buses.py`. Returns 4
  (1 + 3 for the popup), no distance cut-off. Feed time is read as server local time (Warsaw).
- Tests: `cd backend && uv run pytest tests ../algorithms` (`algorithms/` = pure functions, `backend/tests/` = API-level logic that needs no data files).
- Simulation (`algorithms/simulation/`): `record_buses.py` records 2 min of live buses (needs `PORTAL_KEY`) to
  `data/live/bus_track_sample.json` (committed); `simulate_nearest_buses.py` puts users on bus polylines with a GPS
  radius (10-100 m). Results in `algorithms/simulation/RESULTS.md`: own bus always in top-4, top-1 96-100% with
  3 points, 80-89% with 1 point.
- Second run (`artifacts/bus-detection-fraction.html`): point at u * L, u ~ U(0, 1), 10 points per line; same results.
  `rank_buses` is O(V*K*H + V log V), ~2 ms per request for ~880 buses.
- Visualization: `artifacts/bus-detection-simulation.html` (charts, one mini map per line, table), rebuilt with
  `uv run python ../algorithms/simulation/export_viz.py` (same seed, so the same numbers as RESULTS.md).
- Known issue: `bus_detect._epoch` reads feed times in the server's time zone. On a machine in UTC (this dev
  laptop is) bus times end up 2 h ahead of the user's, so time pairing picks the oldest bus report. Fix: parse
  with `ZoneInfo("Europe/Warsaw")` (needs `tzdata` on Windows).
- Feed without a key: mkuran GTFS-RT `vehicles.pb` refreshes about every 20 s; the City Hall feed is the main source.
- `/api/osm/route` returns 422 when a point is more than `MAX_SNAP_M` (1000 m, `osm.py`) from the graph;
  `osm.route()` / `osm.nearest()` in Python have no limit (`report.py` snaps far stops).
- Street cost = length / speed + expected wait at crossings (HCM `(C-g)^2/2C`, constants `SPEED`,
  `WAIT` in `osm.py`). OSM has no signal timing tags in Warsaw.

### Frontend (`frontend/`)

- Stack: React 18, Vite 5, TypeScript, Material UI v6 (+ icons), Leaflet 1.9 with `react-leaflet` 4.
  Node on the dev machine is 18.18, so stay on these versions (newer Vite needs Node 20+).
- Screens, one flow: map with the user's location and start / destination fields on top ->
  list of connection options (with preview on the map) -> chosen route (clean route on the map,
  summary, steps). State lives in `src/App.tsx` (`step`: search / options / route).
- **Routing seam.** `src/api/routes.ts` (`fetchRouteOptions`) calls the backend (`POST /api/routes`)
  when `API_URL` is set, and falls back to the in-browser mock (`mockRouteOptions`) if the backend
  is off/unreachable. Types in `src/types.ts`. The mock's costs and speeds are rough estimates.
- Backend URL: `src/config.ts` reads `VITE_API_URL` (default `http://localhost:8000`;
  set `VITE_API_URL=""` in `frontend/.env` to force the mock).
- Place search: `src/api/geocode.ts` (`searchPlaces`), debounced, limited to Warsaw. Calls the
  backend geocode proxy when `API_URL` is set, else Nominatim directly (≈1 request/second limit).
- Colours: one palette, the Warsaw colours (red + yellow): `src/map/palette.ts` (`PALETTE`, light / dark). Red is the main
  colour in light mode, yellow the accent at night. It sets the map colours, the round map buttons / markers AND the accent
  of the whole UI (the MUI theme in `src/theme.ts` is built from it). The old lavender look and the look switch were removed.
  Colours and icons of transport modes: `src/modes.tsx`.
- Map: flat vector map, OpenFreeMap tiles (no key) drawn by MapLibre GL inside Leaflet (`@maplibre/maplibre-gl-leaflet`, loaded
  on demand). The style is ours: `src/map/mapStyle.ts` (colours from the palette, more labels when zoomed in). Map controls,
  markers and route in `src/components/MapView.tsx`. The old OSM raster map was removed. CARTO basemaps return
  "API KEY REQUIRED", so do not use them. OpenFreeMap has no SLA; there is no fallback.
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
  `rmse_m`, `vehicleNo`, `brigade`); falls back to mock data when the backend is down or there is no location.
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
  engine once per segment and chains the n-th best option of every segment (max 3 options); "optimal" = `algorithms/stop_order.py` (exact, straight-line distance,
  start and destination fixed). Simplifications: every segment is planned from "now", no time at a stop. The frontend mock does the same in `src/api/multiStop.ts`.
- Preferences + filters are UI only (route selection is the backend's job). Model, level tables (default speeds), time
  rules and list filtering: `src/preferences/model.ts`; storage in localStorage key `preferences`
  (`src/preferences/PreferencesProvider.tsx`). Preferences page: `src/components/PreferencesPage.tsx`; reusable fields
  (levels + custom km/h, wheelchair, priorities, excluded districts / own points): `src/components/preferences/`.
  Time rules (`RuleDialog.tsx`) override any section for given days and hours (may cross midnight); the latest started
  active rule wins. `FilterSheet.tsx` = filters for the current search only (sorting, max transfers, vehicles, max walking
  time, step-free, pace / wheelchair, excluded areas, and "Zaawansowane" = all preferences as overrides). Only list-like
  filters really change the (mock) list, client-side (`applyListFilters`); speeds, wheelchair and areas are stored only and
  not passed to `fetchRouteOptions` yet.
- Speed history (device-side, privacy first): in the route view "Rozpocznij przejazd" / "Zakończ" records GPS points (memory only, one every 4 s,
  Screen Wake Lock while recording) and sends the track once to `POST /api/history/records` (`backend/app/api/history.py`,
  `algorithms/speed_history.py::split_track`: shares the moving distance between the route's legs by planned distance, ignores standing
  still and GPS jumps, rejects implausible speeds, walking legs count as `walkAs` = walking or wheelchair). The response has no coordinates;
  the device keeps only these records in localStorage `trip-history` (`src/history/HistoryProvider.tsx`, max 200). The backend stores and logs nothing.
  `POST /api/history/summary` (`summarize`: moving speed = distance / moving time, latest 20 records per mode, outliers ignored, "enough" from 5 trips)
  gives the average per mode; the frontend falls back to `localSummary` when the backend is down. Preferences: each of Pieszo / Rower / Wózek shows
  "Twoja średnia z historii" with "Użyj X km/h" (when it differs by 10% or more) and the switch "Zawsze używaj średniej z historii" (`autoSpeed`; when on and
  enough trips, `applyHistory` in `src/preferences/model.ts` replaces the level / typed speed and the selector is locked). History can be cleared on the Preferences page.
- Backend calls: every call builds its URL with `apiUrl(path)` from `src/config.ts` (routes, geocode, history, vehicle). An empty
  `API_URL` turns all of them to the in-browser mock. Answers are checked in `src/api/validate.ts`; a wrong shape counts as "backend down".
- **Example data is marked.** When a call falls back to the mock, `fetchRouteOptions` / `detectVehicle` return `mock: true`; the app shows
  one snackbar and a "Dane przykładowe" chip on the route list and the vehicle window.
- Hooks (`src/hooks/`): `useLocationTrack` (one `watchPosition` + the last 3 positions, cleaned up on unmount), `useRouteSearch`,
  `useVehicleDetection`. `App.tsx` only wires them. `ErrorBoundary` wraps the app. Selection and step are derived while rendering
  (no effects for derived state). Under the Preferences page the map and panels are `inert`.
- Selectable cards use `pressableProps` (`components/pressable.ts`): Enter / Space select, Space does not scroll. The map has ONE MapLibre
  layer; the light / dark switch calls `setStyle`. Leaflet marker icons are plain SVG from `ICON_PATH` in `modes.tsx` (no `react-dom/server`).
- Checks: `npm run lint` (ESLint 8, `.eslintrc.cjs`), `npm test` (Vitest 1 + Testing Library), `npm run build`.
- Vite proxies `/api` to the backend at http://localhost:8000.
- Layout is mobile first; from 600 px (`sm`) the panels sit on the left side.
- Design references (user's screenshots): ride-choice list (selected card outlined), dark map with
  a clean route and round stop markers, light map with a bottom sheet.
- Run: `npm install`, `npm run dev` (http://localhost:5173), `npm run build` (type-check + build).

### Backend — routing API (`backend/app/`)

- Separate package `backend/app/` holds the route models and `RealRouteEngine`. `backend/main.py`
  mounts it, so one uv process serves data, geocode and `POST /api/routes`.
- Models (`app/models.py`) mirror `frontend/src/types.ts` exactly (camelCase JSON keys; `from`
  via a Pydantic alias). FastAPI serializes responses by alias, so the output matches the UI types.
- Endpoints: `POST /api/routes` -> `RouteOption[]` (backend side of `fetchRouteOptions`),
  `GET /api/geocode?q=` -> `Place[]` (Nominatim proxy, Warsaw-limited), `GET /health` on `app.main`.
- Routing is behind a `RouteEngine` seam (`app/routing/engine.py`): `query_routes(...)` and
  `update_state(...)`. Current impl is `RealRouteEngine` (GTFS + OSM + Veturilo). `StubRouteEngine`
  is the old mock. A `CppRouteEngine` can replace the real engine later; nothing else changes.
- The Python<->C++ wire format is owned by the C++ team (not defined yet). Python will keep the
  C++ service current via `update_state` (live data) and delegate routing via `query_routes`.
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
  and answers 503 while `READY` is cleared (cache warm-up at start, `mkuran.warm()` + `osm.warm()`).
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
