# feature/veturilo-min-bikes

- Router `POST /state {"veturilo": {"vet:<id>": bikes}}`: replaces the live Veturilo state (docks left out = no data).
- `/plan` `min_bikes` (per query, default 0 = every dock): rent only at docks with at least that many bikes. The state
  is read once at the start of the query and stays frozen, so availability does not depend on the arrival time
  (RAPTOR's "earlier is never worse" holds). Returning is allowed at every dock (free places not checked).
- Veturilo legs carry `bikes` (pickup dock, frozen state); `/health` has `state.veturilo {docks, age_s}`.
- Backend: `street_router.push_state()` sends `nextbike.status()` every 30 s (a dock that does not rent = 0 bikes).
- Tests: `algorithms/test_raptor.py` (`/state` + `min_bikes` cases, brute force with only the pickup docks).
- Part of #95.
