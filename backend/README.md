# Backend

The backend is one FastAPI app, started with uv. It downloads and parses the open-data sources
(GTFS, Veturilo GBFS, OSM, City Hall live APIs) and answers `POST /api/routes` from that data.
`app/` holds the route models and `RealRouteEngine`; `main.py` mounts them.

---

## 1. Data layer (uv)

```bash
cd backend
uv sync                              # install deps (Python 3.12, .venv)
uv run python download.py            # download all sources (or: download.py mkuran|um_warszawa|nextbike|osm|siting)
uv run uvicorn main:app --reload     # data + routes + geocode at http://localhost:8000, docs at /docs
uv run python report.py              # write ../data/REPORT.md and ../data/report.json
```

- Keys come from `../.env` (`PORTAL_KEY`, `WAW_API_KEY`, see `../ACCESS.md`). Only the City Hall
  endpoints need them.
- At start the server builds its caches in `../data/derived/` (GTFS ~25 s, OSM ~17 s on the first run,
  `stations.json`) and starts the C++ street router (`street_router.py`, build it first: `../algorithms/router/README.md`).
  Until then the endpoints that need them answer 503.
- Endpoints: `/api/sources`, `/api/stats`, one router per source, `/api/live/nearest-buses` and `/api/live/delay`
  (`bus_detect.py`), `/api/stations` (`api_stations.py`), `POST /api/routes`, `GET /api/geocode`, `/api/history/*`,
  `POST /api/journeys`, and `/api/sim/*` in simulation mode (`sim/`).
- `POST /api/routes` uses `app/routing/real_engine.py` (GTFS departures, street paths from the C++ router, live Veturilo).
- See `../data/REPORT.md` for sources, ID compatibility, graph sizes and the full endpoint list.
- The API reference of both parts is `../data/API.md`. It is the contract: code must match it, and every PR
  keeps it up to date.

## 2. Routes

`POST /api/routes`, `GET /api/geocode`, `/api/history/*` and `POST /api/journeys` are mounted by `main.py` (the uv app
above). `app/` is the engine and the models, not a second server to start (`app/main.py` is the old slim app).

- Body `{ "from": Place, "to": Place, "profile": "standard" }` -> `RouteOption[]`.
- A missing GTFS zip returns `503`.
- `ROUTE_ENGINE` picks the engine (`app/routing/factory.py`): `real` (default, the only one).
- `requirements.txt` is the old slim app. It cannot import the timetable. Use uv.

### Config (environment variables, all optional)

- `CORS_ORIGINS` — comma-separated allowed origins
  (default `http://localhost:5173,http://127.0.0.1:5173`).
- `NOMINATIM_URL` — geocoding endpoint (default public Nominatim).
- `NOMINATIM_USER_AGENT` — required by Nominatim's usage policy.
- Other variables (keys, `ROUTER_URL`, `ROUTER_PORT`, `ROUTE_ENGINE`, `SIM_SCENARIO`, `LIVE_BUSES_URL`,
  `DELAY_RADIUS_M`, `JOURNEY_STATS_DB`): see "Environment setup (for agents)" in `../README.md`.

### Structure (`app/`)

```
app/
  main.py              old slim FastAPI app (routes, geocode, history, journeys, /health)
  config.py            settings from env vars
  models.py            Pydantic models mirroring frontend types
  api/
    routes.py          POST /api/routes
    geocode.py         GET  /api/geocode (our stops and Veturilo stations, then Nominatim)
    history.py         POST /api/history/records, /api/history/summary (speed history, stateless)
    journeys.py        POST /api/journeys (opt-in journey statistics)
  routing/
    engine.py          RouteEngine interface (seam for the C++ service)
    factory.py         picks the engine from ROUTE_ENGINE
    real_engine.py     routes from GTFS, street paths and Veturilo; legs_from_router() = the router adapter
    geometry.py        leg shapes for drawing (router street path, GTFS shape, else a polyline)
    multi.py           trips with intermediate stops
    geo.py             geometry and time helpers
```

### Frontend connection

The frontend calls this API when `VITE_API_URL` is set (default `http://localhost:8000`). If the
backend is unreachable it says "Nie połączono z serwerem" (no made-up routes). Set `VITE_API_URL=""` in
`frontend/.env` to use the in-browser example data.
