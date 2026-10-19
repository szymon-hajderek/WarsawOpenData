# docs/delay-radius-report

Optimal radius R for the delay estimate, as a report, and the new default.

- `search_delay_radius.py --report` writes `artifacts/delays/tests/radius-search.html` (template
  `artifacts/delays/templates/radius-search.html`): the two-step search (20–200 m every 10 m, then every 1 m between the
  two best neighbours), chart of score and availability, full tables, the pick. Rerun on 2026-10-18 on the 2026-10-17
  recording: best R = 80 m (96.5%), 30 m = 95.0%, flat from 80 m.
- Default `DELAY_RADIUS_M` is now 80 m (was 30 m): `backend/bus_detect.py`, `.env.example`, `README.md`, `AGENTS.md`,
  `data/API.md` (the two example answers there were recorded with 30 m and say so). Simulation scripts default to 80 m.
- `artifacts/delays/delay-statistics.html` rebuilt at 80 m (100% of passes have a delay, median error 2 s, p90 14 s);
  `delay-docs.html`, `tests/delay-tests.html` and `artifacts/README.md` updated and linked to the report.

Note: a local `.env` that still sets `DELAY_RADIUS_M=30` keeps the old radius.
