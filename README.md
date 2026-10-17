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
- "Which vehicle am I in?" window (mock data).
- Data download and parsers for GTFS, City Hall live APIs, Veturilo (GBFS) and the OSM street graph.
- FastAPI endpoints for every data source.

Planned:

- **Real routing** with OpenTripPlanner (GTFS, GBFS, OSM).
- **Multi-stop routes.** Plan one trip through many places, with many means of transport.
- **Online route planning.** Change the route while the user travels.
- **Live delays.** Use real-time vehicle data to find the fastest route now.

## Tech stack

- Frontend: React + TypeScript + Vite, Material UI, Leaflet + MapLibre (OpenFreeMap tiles)
- Backend: Python + FastAPI, managed with uv
- Routing: OpenTripPlanner (planned)
- Database: none for now, raw files in `data/`

## Folder structure

- `frontend/` — React app
- `backend/` — FastAPI app, data download and parsers (see `backend/README.md`)
- `data/` — datasets and the data report `data/REPORT.md`
- `algorithms/`, `db/`, `routing/` — placeholders for the next steps
- `ui/` — UI concept art
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
3. **Data** (`data/`). GTFS zips and the OSM extract are stored with Git LFS.
   - install Git LFS once: `brew install git-lfs && git lfs install`, then `git lfs pull`
   - or download fresh copies: `cd backend && uv run python download.py` (about 250 MB)
4. **Backend** (`backend/`, Python + FastAPI, managed with [uv](https://docs.astral.sh/uv/)).
   - install uv: `brew install uv` (or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - `cd backend && uv sync` installs Python 3.12 and all dependencies (`osmium`, `scipy`, `fastapi` ...)
   - run every backend command from `backend/`
   - `uv run uvicorn main:app --reload` starts the API at http://localhost:8000 (docs at `/docs`)
   - `uv run python report.py` rebuilds `data/REPORT.md` (sources, ID links, graph sizes, endpoints)
   - the first request that needs GTFS / OSM builds caches in `data/derived/` (~25 s / ~45 s)
5. **Routing, database, Docker.** Not set up yet (OpenTripPlanner, PostgreSQL + PostGIS, Docker).
