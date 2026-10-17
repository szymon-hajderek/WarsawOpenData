# Backend

The backend is one FastAPI app, started with uv. It downloads and parses the open-data sources
(GTFS, Veturilo GBFS, OSM, City Hall live APIs) and answers `POST /api/routes` from that data.
`app/` holds the route models and `RealRouteEngine`; `main.py` mounts them.

---

## 1. Data layer (uv)

```bash
cd backend
uv sync                              # install deps (Python 3.12, .venv)
uv run python download.py            # download all sources (or: download.py mkuran|um_warszawa|nextbike|osm)
uv run uvicorn main:app --reload     # data + routes + geocode at http://localhost:8000, docs at /docs
uv run python report.py              # write ../data/REPORT.md and ../data/report.json
```

- Keys come from `../.env` (`PORTAL_KEY`, `WAW_API_KEY`, see `../ACCESS.md`). Only the City Hall
  endpoints need them.
- The first call that needs GTFS or OSM builds caches in `../data/derived/` (~25 s and ~45 s).
- Endpoints: `/api/sources`, `/api/stats`, one router per source, `POST /api/routes`, `GET /api/geocode`.
- `POST /api/routes` uses `app/routing/real_engine.py` (GTFS departures, OSM paths, live Veturilo).
  The first route request builds the GTFS cache (~25 s) and, for a street path, the OSM graph (~45 s).
- See `../data/REPORT.md` for sources, ID compatibility, graph sizes and the full endpoint list.
- The API reference of both parts is `../data/API.md`. It is the contract: code must match it, and every PR
  keeps it up to date.

## 2. Routes

`POST /api/routes` and `GET /api/geocode` are mounted by `main.py` (the uv app above).
`app/` is the engine and the models, not a second server to start.

- Body `{ "from": Place, "to": Place, "profile": "standard" }` -> `RouteOption[]`.
- A missing GTFS zip returns `503`.
- `StubRouteEngine` is the previous mock and is not used.
- `requirements.txt` is the old slim app. It cannot import the timetable. Use uv.

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
    real_engine.py     routes from GTFS, OSM and Veturilo
    stub_engine.py     old mock, not used
    geo.py             time helpers
```

### Frontend connection

The frontend calls this API when `VITE_API_URL` is set (default `http://localhost:8000`). If the
backend is unreachable it falls back to the in-browser mock. Set `VITE_API_URL=""` in
`frontend/.env` to force the mock.
