# docs/refresh-stale-docs

Docs only, no behaviour change: stale documentation brought in line with `main`.

- `AGENTS.md`: status / tech stack / folder structure reflect the running C++ street router (RAPTOR planned);
  rail platforms (`pkp:<station>_P<n>`), SKM from `polish_trains.zip`, `NO_STEPS` incl. stroller, cache rebuild rules,
  `osm.route()` removed, warm-up steps, Node 26 test flag, phone `VITE_API_URL`, which frontend calls use `apiUrl`.
- `README.md`: status and features, street router build, matrices optional, HTTPS on a phone with `VITE_API_URL`, Node.
- `data/API.md`: speed history endpoints (`/api/history/records`, `/api/history/summary`) with real examples,
  table of contents fixed, `/health` only on the slim app, GTFS stop fields `platform` / `members` / `boarding`,
  current `/api/stats`, `/api/osm/graph/summary`, `/api/stations/report` examples, 503 list.
- `algorithms/router/README.md`: `/route` answer (`legs`, `segments`, example), `points.csv` columns, four modes,
  last run on the overlay, in-station metro transfers (no longer a known gap), report section 5.
- `backend/README.md`, `frontend/README.md`, `integration/README.md`, `artifacts/README.md`, `ACCESS.md`: commands,
  files and endpoints that changed.
- False comments fixed: `backend/bus_detect.py` (feed source), `frontend/src/config.ts` (no silent mock fallback),
  `.env.example` (`LIVE_BUSES_URL`).
