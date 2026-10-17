# docs/api-markdown

- Added `data/API.md`: the reference of all 26 backend endpoints (data API 23 + routing API 3) (parameters, answer fields, errors, real JSON examples).
- `AGENTS.md`: every PR checks and updates `data/API.md`; the file is the contract and code must follow it.
- Linked `data/API.md` in `README.md` and `backend/README.md`.
- Fixed: `backend/main.py` started the bus poller with `app.add_event_handler`, which the locked FastAPI 0.143
  does not have, so `uvicorn main:app` failed. It now uses `lifespan`.
- Fixed: `/api/osm/nearest` and `/api/osm/route` returned 500 for a `mode` other than `walk` / `bike`;
  they now return 400, like `/api/osm/graph/summary` (shared `check_mode` in `osm.py`).
- The two bugs found while writing the examples (`add_event_handler` at startup, `500` for a bad OSM `mode`) were fixed on this branch.
