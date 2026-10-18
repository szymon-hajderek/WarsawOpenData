# feature/remove-python-planner

User decision: no silent fallback; transit comes only from the router's `POST /plan`.

- `real_engine`: `/health` not ready or `/plan` 501 / 503 -> `POST /api/routes` 503
  `{"detail": "transit timetable not ready"}` (or the router's message). The walk comes from `/route` when `/plan`
  gives no street-only trip.
- Removed the Python transit planner: `_query`, the Veturilo / transit builders, live delay shift (`_delay`,
  `algorithms/lateness.py`), footpaths, the planner functions of `algorithms/plan_trip.py` (only the Warsaw clock
  helpers stay) and their tests. `integration/gtfs/test_delay.py` is skipped (no delay shift any more).
- Kept: street-only `travel`, multi-stop, excluded areas, `excludeModes`.
- Docs: `data/API.md`, AGENTS.md, README.md, `backend/README.md`.
