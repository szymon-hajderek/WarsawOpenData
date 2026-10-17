# feature/integration-sim-backend

Integration tests: synthetic trips on real data, against the whole backend in simulation mode.

- `backend/sim/`: one clock for the backend (`clock.py`), scenarios (`scenario.py`: recorded feed replay or
  vehicles from GTFS, Veturilo changes, alerts, delays), synthetic vehicles from timetable + shapes (`synth.py`),
  `/api/sim/*` endpoints (`api.py`, only with `SIM_SCENARIO`, in `data/API.md`).
- Live sources read the scenario in simulation mode (`um_warszawa`, `nextbike`, `alerts`); `TTLCache` does not
  cache then; `bus_detect`, the route engine and departures read the time from `sim.clock`.
- Time zone fix: feed times and GTFS service midnights are read as Europe/Warsaw (`zoneinfo`), not the
  server's zone, so bus detection and delay work on a server in UTC.
- `ROUTE_ENGINE` env picks the engine (`app/routing/factory.py`). A new engine must pass `integration/`
  before it replaces `real` (note in `integration/README.md` and `engine.py`).
- `integration/`: `recorded/` (2-minute recording) and `gtfs/` (synthetic) tests, markers `recorded` / `gtfs`,
  synthetic user (`journey.py`), `RESULTS.md` with metrics and checks.
- Found: realistic phone fixes lower top-1 detection to about 80% on the recording; `lateness.py` measures delay
  at the nearest stop (4 min shows as 3 min); the engine returns options that leave hours after the query
  (night buses for 08:30) and sometimes no option at all (strict xfail in `test_engine_sanity.py`).
