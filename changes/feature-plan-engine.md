# feature/plan-engine

Issue #94: the route engine plans transit trips with the router's RAPTOR (`POST /plan`).

- `real_engine._plan`: one `/plan` call (mode from the profile / step-free, `speeds`, `max_legs` = maxTransfers + 1,
  `veturilo_s: 0` when cycling is off) plus one later query (+60 s) for the next departures.
- Every leg goes through `legs_from_router`; options get title (lines joined by " + ", "Veturilo"), id
  `pt-<trip ids>` (route-delays reads it), departure / arrival from `dep_s` / `arr_s`, transfers, waitS, tags
  ("Najszybsza", "Zmiana na trasie", step-free / elevators).
- Kept: excluded-area filter, street-only `travel`, multi-stop, the walk option (dropped above 50 min), max 6 options.
- Fallback to the Python planner (logged) when `/health` says the timetable / plan of the mode is not ready or
  `/plan` answers 501 / 503. `/plan` 404 / 422 gives an empty list; router down = 503.
- Tests: `backend/tests/test_plan_engine.py`. `data/API.md` and AGENTS.md updated.
