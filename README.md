# WarsawOpenData

Route planner for Warsaw. It combines Veturilo (city bikes) with public transport at every stage of a trip.
A 24-hour hackathon project built on Warsaw open data.

> **Status:** proof of concept. The frontend UI works with **mock routing**. The backend downloads and parses
> the data and serves it through FastAPI. Real routing is not built yet.

## Goal

1. The user sets a start (own location or typed) and a destination.
2. The app shows n connection options that use Veturilo at any stage.
3. The user picks one and sees the route on the map, with a summary and steps.

The project aims at inclusivity (walking, cycling and stroller pace), safety, privacy and scalability to other cities.

## Features

Done:

- Map UI in Polish: start / destination fields, list of options, route preview, route details (mock data).
- Two map looks (`lavender`, `warsaw`), light and dark mode.
- "Which vehicle am I in?" window: nearest live buses by MSE (`POST /api/live/nearest-buses`).
- Data download and parsers for GTFS, City Hall live APIs, Veturilo (GBFS) and the OSM street graph.
- FastAPI endpoints for every data source.

Planned:

- **Real routing** with a custom C++ engine. It builds its own graph at startup. Python then sends only live data and values derived from it.
- **Multi-stop routes.** Plan one trip through many places, with many means of transport.
- **Online route planning.** Change the route while the user travels.
- **Live delays.** Use real-time vehicle data to find the fastest route now.

## Tech stack

- Frontend: React + TypeScript + Vite, Material UI, Leaflet + MapLibre (OpenFreeMap tiles)
- Backend: Python + FastAPI (data layer managed with uv; routing API in `backend/app/` uses venv)
- Routing: custom C++ engine (planned); FastAPI is a thin backend in front of it
- Database: none for now, raw files in `data/`

## Folder structure

- `frontend/` — React app
- `backend/` — FastAPI app, data download and parsers (see `backend/README.md`)
- `data/` — datasets, the API reference `data/API.md` and the data report `data/REPORT.md`
- `algorithms/`, `db/`, `routing/` — placeholders for the next steps
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
- OpenStreetMap street graph (BBBike extract)

Details, ID links and graph sizes: `data/REPORT.md`.

## Environment setup (for agents)

Follow these steps to get a working environment. Run them from the repo root.
Keep this section current: every PR that adds a dependency or a tool updates it.

1. **Keys.** Copy `.env.example` to `.env` and fill in the keys. See `ACCESS.md`. Never commit `.env`.
2. **Frontend** (`frontend/`). Needs Node 18.18 or newer 18.x.
   - `cd frontend && npm install` (if `~/.npm` is root-owned: `npm install --cache <some dir>`)
   - `npm run dev` starts the app at http://localhost:5173
   - `npm run build` type-checks and builds
   - `npm run lint` runs ESLint (react-hooks + jsx-a11y rules); `npm test` runs the Vitest tests (jsdom, no browser needed)
   - optional: `VITE_API_URL` in `frontend/.env` points the app at the routing API
     (default `http://localhost:8000`; set `VITE_API_URL=""` to force the in-browser mock)
3. **Data** (`data/`). GTFS zips and the OSM extract are stored with Git LFS.
   - install Git LFS once: `brew install git-lfs && git lfs install`, then `git lfs pull`
   - or download fresh copies: `cd backend && uv run python download.py` (about 250 MB)
4. **Backend** (`backend/`, Python + FastAPI, managed with [uv](https://docs.astral.sh/uv/)).
   - install uv: `brew install uv` (or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - `cd backend && uv sync` installs Python 3.12 and all dependencies (`osmium`, `scipy`, `fastapi` ...)
   - run every backend command from `backend/`
   - `uv run uvicorn main:app --reload` starts the API at http://localhost:8000 (docs at `/docs`).
     This one process serves the data, geocode and `POST /api/routes` (real GTFS + OSM + Veturilo).
   - `uv run python report.py` rebuilds `data/REPORT.md` (sources, ID links, graph sizes, endpoints)
   - the server builds the GTFS / OSM caches in `data/derived/` at start (~25 s / ~45 s on the first run, a minute or two
     with a ready cache). Until then `/api/gtfs`, `/api/osm` and `/api/routes` answer 503 (`Retry-After: 30`)
   - `uv run pytest tests ../algorithms` runs the tests (pytest is in the `dev` group, installed by `uv sync`)
   - bus detection simulation: `uv run python ../algorithms/simulation/simulate_nearest_buses.py`
     (uses the committed sample; record a new one with `uv run python ../algorithms/simulation/record_buses.py`, needs `PORTAL_KEY`)
   - rebuild the results page `artifacts/bus-detection-simulation.html`: `uv run python ../algorithms/simulation/export_viz.py`
   - optional `.env` setting `LIVE_BUSES_URL`: where bus detection reads live bus positions (default: the City Hall feed via `PORTAL_KEY`). Without `PORTAL_KEY` the live-vehicle poller stays off and `GET /api/live/vehicles` returns 503.
   - optional `.env` setting `DELAY_RADIUS_M`: radius for the delay estimate `GET /api/live/delay` (default `30`)
   - delay simulation on the committed recording `data/live/delay_sample.json.gz`: `uv run python ../algorithms/simulation/simulate_delay.py --radius 30`;
     rebuild the report `artifacts/delay-simulation.html`: `uv run python ../algorithms/simulation/export_delay_viz.py`;
     search the best radius (20-200 m every 10 m, then every 1 m): `uv run python ../algorithms/simulation/search_delay_radius.py`;
     record a new sample (server running, 30 min): `uv run python ../algorithms/simulation/record_delay_sample.py 30`
   - tune that radius on live data (needs `PORTAL_KEY`): `uv run python ../algorithms/simulation/tune_delay_radius.py 8`
5. **Routes** are part of the uv app in step 4. Do not start a second server on port 8000.
   The package `backend/app/` is the route engine imported by `main.py`. `requirements.txt` is only
   the old slim app and cannot load the timetable (it has no numpy/scipy).
6. **Database, Docker.** Not set up yet (PostgreSQL + PostGIS, Docker). The C++ routing engine is
   planned (a long-running service that builds its own graph at startup; Python then sends only live updates).
