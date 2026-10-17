# WarsawOpenData

Route planner for Warsaw.

> **Status:** early idea. There is no code yet.

## Planned features

- **Multi-stop routes.** Plan one trip through many places, with many means of transport.
- **Online route planning.** Change the route while the user travels.
- **Live delays.** Use real-time vehicle data to find the fastest route now.

## Data

- [Warsaw city API portal](https://api.um.warszawa.pl/)

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
