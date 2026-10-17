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
- **Status:** the frontend UI exists. The backend has two parts: a **data layer** (download,
  parsers and FastAPI endpoints for all sources, `backend/`, report in `data/REPORT.md`) and a
  **routing API** (`backend/app/`) with a stub routing engine (ported mock) + a geocode proxy.
  The real C++ routing engine is not built yet.

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
- `backend/` — FastAPI app
- `algorithms/` — algorithms (mandatory folder): pure functions + their pytest files (`nearest_buses.py`)
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
  `/api/live/vehicles?type=bus`) every 10 s and keeps the last 3 positions per vehicle in memory.
  `POST /api/live/nearest-buses` ranks buses by MSE (m^2) between the user's 1-3 points and each bus track
  (each user point paired with the bus point closest in time), `algorithms/nearest_buses.py`. Returns 4
  (1 + 3 for the popup), no distance cut-off. Feed time is read as server local time (Warsaw).
- Tests: `cd backend && uv run pytest ../algorithms`.
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
- Colours: every colour of the app lives in `src/map/looks.ts` (one table: look x light / dark). A **look** sets the
  map colours, the round map buttons / markers AND the accent of the whole UI (the MUI theme in `src/theme.ts` is built
  from it, so panels, chips and windows follow the look). Colours and icons of transport modes: `src/modes.tsx`.
- Two looks, switched with the layers button on the map (saved in localStorage key `map-variant`, `src/mapLook.tsx`;
  `lavender` is the default, `warsaw` = red + yellow: red is the main colour in light mode, yellow the accent at night):
  - Both use the same flat vector map: OpenFreeMap tiles (no key) drawn by MapLibre GL inside Leaflet
    (`@maplibre/maplibre-gl-leaflet`, loaded on demand). The style is ours: `src/map/mapStyle.ts` (colours from the look,
    more labels when zoomed in). Map controls, markers and route in `src/components/MapView.tsx`.
  - The old OSM raster map (v1) was removed. CARTO basemaps return "API KEY REQUIRED", so do not use them.
    OpenFreeMap has no SLA; there is no fallback.
- "Which vehicle am I in?" window (`src/components/VehicleSheet.tsx`): open on the start screen, swipe down / tap to hide
  into a bar, swipe up / tap to bring it back. Shows the suggested vehicle (mode + line + direction) and 3 others;
  "Jadę tą linią" confirms, "Nie jadę komunikacją" closes it until reload. Data: `src/api/vehicle.ts`
  (`detectVehicle`) sends the user's last 1-3 positions (memory only, one every 10 s) to
  `POST /api/live/nearest-buses`; falls back to mock data when the backend is down. Detection runs once
  after start and again on `requestLinePopup()` (for a "choose my line" button). Each detection sends a
  `bus-popup` event on `window` (`{ candidates, lines, points }`; `lines` = all live lines, for manual choice).
  Live buses have no direction yet (`direction: ""`). Concept: `ui/concept-art/current-line-popup.paint`.
- Navigation: bottom bar (`src/components/BottomNav.tsx`) with tabs Mapa and Preferencje; floating panels sit above it
  (`src/layout.ts`: `BOTTOM_NAV_HEIGHT`, `PANEL_BOTTOM`). The Preferences page is an overlay, the map stays mounted below.
- Preferences + filters are UI only (route selection is the backend's job). Model, level tables (default speeds), time
  rules and list filtering: `src/preferences/model.ts`; storage in localStorage key `preferences`
  (`src/preferences/PreferencesProvider.tsx`). Preferences page: `src/components/PreferencesPage.tsx`; reusable fields
  (levels + custom km/h, wheelchair, priorities, excluded districts / own points): `src/components/preferences/`.
  Time rules (`RuleDialog.tsx`) override any section for given days and hours (may cross midnight); the latest started
  active rule wins. `FilterSheet.tsx` = filters for the current search only (sorting, max transfers, vehicles, max walking
  time, step-free, pace / wheelchair, excluded areas, and "Zaawansowane" = all preferences as overrides). Only list-like
  filters really change the (mock) list, client-side (`applyListFilters`); speeds, wheelchair and areas are stored only and
  not passed to `fetchRouteOptions` yet.
- Vite proxies `/api` to the backend at http://localhost:8000.
- Layout is mobile first; from 600 px (`sm`) the panels sit on the left side.
- Design references (user's screenshots): ride-choice list (selected card outlined), dark map with
  a clean route and round stop markers, light map with a bottom sheet.
- Run: `npm install`, `npm run dev` (http://localhost:5173), `npm run build` (type-check + build).

### Backend — routing API (`backend/app/`)

- Separate from the data layer above: the data layer serves raw sources; this part serves the
  frontend (routes + geocode). They live side by side in `backend/` and today run as two apps.
- Stack: Python + FastAPI, run with `uvicorn app.main:app --reload`. Deps in `requirements.txt`
  (fastapi, uvicorn, httpx); use a `venv`. No database. See `backend/README.md`.
- Models (`app/models.py`) mirror `frontend/src/types.ts` exactly (camelCase JSON keys; `from`
  via a Pydantic alias). FastAPI serializes responses by alias, so the output matches the UI types.
- Endpoints: `POST /api/routes` -> `RouteOption[]` (backend side of `fetchRouteOptions`),
  `GET /api/geocode?q=` -> `Place[]` (Nominatim proxy, Warsaw-limited), `GET /health`.
- Routing is behind a `RouteEngine` seam (`app/routing/engine.py`): `query_routes(...)` and
  `update_state(...)`. Current impl is `StubRouteEngine` (`app/routing/stub_engine.py`), a 1:1
  port of the frontend mock. Swap it for a `CppRouteEngine` later; nothing else changes.
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
