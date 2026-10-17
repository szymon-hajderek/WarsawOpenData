# Backend (FastAPI)

Thin Python backend for the WarsawOpenData route planner. No database yet.
Routing is behind a `RouteEngine` seam; today it uses a **stub** that ports the
frontend mock, so the whole app works end-to-end. The stub will later be
replaced by a `CppRouteEngine` talking to a long-running C++ routing service
(graph + live state kept in memory on the C++ side).

## Run

```bash
cd backend
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs

## Endpoints

- `POST /api/routes` — body `{ "from": Place, "to": Place, "profile": "standard" }`,
  returns `RouteOption[]`. This is the backend side of the frontend's
  `fetchRouteOptions`. Shapes match `frontend/src/types.ts`.
- `GET /api/geocode?q=<text>` — proxy to OpenStreetMap Nominatim (limited to
  Warsaw), returns `Place[]`. Mirrors the frontend's `searchPlaces`.
- `GET /health` — liveness check.

## Config (environment variables, all optional)

- `CORS_ORIGINS` — comma-separated allowed origins
  (default `http://localhost:5173,http://127.0.0.1:5173`).
- `NOMINATIM_URL` — geocoding endpoint (default public Nominatim).
- `NOMINATIM_USER_AGENT` — required by Nominatim's usage policy.

## Structure

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

## Frontend connection

The frontend calls this backend when `VITE_API_URL` is set (default
`http://localhost:8000`). If the backend is unreachable it falls back to the
in-browser mock. Set `VITE_API_URL=""` in `frontend/.env` to force the mock.
