# docs/api-markdown

- Added `data/API.md`: the reference of all 23 backend endpoints (parameters, answer fields, errors, real JSON examples).
- `AGENTS.md`: every PR checks and updates `data/API.md`; the file is the contract and code must follow it.
- Linked `data/API.md` in `README.md` and `backend/README.md`.
- Found, not fixed: `backend/main.py` calls `app.add_event_handler`, which the locked FastAPI 0.143 does not have,
  so `uvicorn main:app` fails to start. Examples were taken with the poller start left out.
- Found, not fixed: `/api/osm/nearest` and `/api/osm/route` return 500 for a `mode` other than `walk` / `bike`.
