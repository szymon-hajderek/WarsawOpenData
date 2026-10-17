# Backend

The backend has **two parts** that live side by side in `backend/` and today run as two apps:

1. **Data layer** — downloads and parses the open-data sources (GTFS, Veturilo GBFS, OSM, City
   Hall live APIs) into `../data/`. Flat layout (`main.py`, `config.py`, `sources/`), managed with
   **uv**. No database: raw files live in `../data/`.
2. **Routing API** (`app/`) — serves the frontend: route options and a geocode proxy. Package
   layout (`app/`), managed with **venv + requirements.txt**. Routing is behind a `RouteEngine`
   seam; today a stub ports the frontend mock, later a `CppRouteEngine` talks to a long-running
   C++ routing service (graph + live state in memory).

---

## 1. Data layer (uv)

```bash
cd backend
uv sync                              # install deps (Python 3.12, .venv)
uv run python download.py            # download all sources (or: download.py mkuran|um_warszawa|nextbike|osm)
uv run uvicorn main:app --reload     # data API at http://localhost:8000, docs at /docs
uv run python report.py              # write ../data/REPORT.md and ../data/report.json
```

- Keys come from `../.env` (`PORTAL_KEY`, `WAW_API_KEY`, see `../ACCESS.md`). Only the City Hall
  endpoints need them.
- The first call that needs GTFS or OSM builds caches in `../data/derived/` (~25 s and ~45 s).
- Endpoints: `/api/sources`, `/api/stats`, plus one router per source.
- See `../data/REPORT.md` for sources, ID compatibility, graph sizes and the full endpoint list.
- The API reference of both parts is `../data/API.md`. It is the contract: code must match it, and every PR
  keeps it up to date.

## 2. Routing API (venv)

```bash
cd backend
python -m venv .venv                 # on this machine use `py -m venv .venv` (python is a Store alias)
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # routing API at http://localhost:8000, docs at /docs
```

- `POST /api/routes` — body `{ "from": Place, "to": Place, "profile": "standard" }`, returns
  `RouteOption[]`. Backend side of the frontend's `fetchRouteOptions`. Shapes match
  `frontend/src/types.ts`.
- `GET /api/geocode?q=<text>` — proxy to OpenStreetMap Nominatim (limited to Warsaw), returns
  `Place[]`. Mirrors the frontend's `searchPlaces`.
- `GET /health` — liveness check.

### Config (environment variables, all optional)

- `CORS_ORIGINS` — comma-separated allowed origins
  (default `http://localhost:5173,http://127.0.0.1:5173`).
- `NOMINATIM_URL` — geocoding endpoint (default public Nominatim).
- `NOMINATIM_USER_AGENT` — required by Nominatim's usage policy.

### Structure (`app/`)

```
app/
  main.py              FastAPI app, CORS, routers, /health
  config.py            settings from env vars
  models.py            Pydantic models mirroring frontend types
  api/
    routes.py          POST /api/routes
    geocode.py         GET  /api/geocode (Nominatim proxy)
  routing/
    engine.py          RouteEngine interface (seam for the C++ service)
    stub_engine.py     StubRouteEngine (ported frontend mock)
    geo.py             geometry/time helpers (ported from the frontend)
```

### Frontend connection

The frontend calls this API when `VITE_API_URL` is set (default `http://localhost:8000`). If the
backend is unreachable it falls back to the in-browser mock. Set `VITE_API_URL=""` in
`frontend/.env` to force the mock.

> Note: both parts default to port 8000. Run only one at a time, or give one a different `--port`.
> Merging them into a single FastAPI app is a later cleanup.
