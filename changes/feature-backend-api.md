# Changes on `feature/backend-api`

First version of the Python backend (FastAPI), no database.

## Backend (`backend/`)

- FastAPI app (`app/main.py`) with CORS for the Vite dev server and a `/health` check.
- Pydantic models (`app/models.py`) mirror the frontend contract in
  `frontend/src/types.ts` (`Place`, `RouteLeg`, `RouteOption`, `Profile`, ...).
  JSON keys match the frontend (camelCase; `from` via alias).
- Endpoints:
  - `POST /api/routes` -> `RouteOption[]` — backend side of the frontend's
    `fetchRouteOptions`.
  - `GET /api/geocode?q=` -> `Place[]` — proxy to OpenStreetMap Nominatim
    (Warsaw-limited), mirrors the frontend's `searchPlaces`.
- Routing is behind a `RouteEngine` seam (`app/routing/engine.py`). The only
  implementation today is `StubRouteEngine` (`app/routing/stub_engine.py`), a 1:1
  port of the frontend mock, so the app works end-to-end without a database or C++.
- Geometry/time helpers ported from the frontend in `app/routing/geo.py`.
- `requirements.txt` (fastapi, uvicorn, httpx) + `README.md` with run instructions.

### Future C++ engine (seam ready, not implemented)

- `RouteEngine` has `query_routes(...)` and `update_state(...)`. The plan is a
  long-running C++ service that keeps the graph and live state in memory; Python
  stays a thin backend that fetches external APIs and pushes updates into C++.
  A future `CppRouteEngine` implements the interface; nothing else changes.
- The exact Python<->C++ wire format is owned by the C++ team (TODO).

## Frontend wiring

- `src/config.ts`: `API_URL` from `VITE_API_URL` (default `http://localhost:8000`;
  set `""` to force the mock).
- `src/api/routes.ts`: `fetchRouteOptions` now calls `POST /api/routes`, with a
  fallback to the in-browser mock (`mockRouteOptions`) if the backend is off/unreachable.
- `src/api/geocode.ts`: `searchPlaces` now calls the backend proxy, with a
  fallback to calling Nominatim directly.

## Not included (by decision)

- No database, no real C++ engine (only the interface + stub), no Docker.
