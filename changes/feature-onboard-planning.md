# feature/onboard-planning

Planning from the vehicle the user is in. Timetable only, no live delays (user decision).

- `RouteRequest.onboard: {vehicleId}` (ids as in `POST /api/live/nearest-buses`).
- `app/routing/onboard.py`: trip + next stop from `bus_detect._delay_for` (delay ignored), the next two stops of the
  trip at their scheduled arrival are `/plan` origins (`RealRouteEngine.query_from_stop`, `from` = stop id).
- A ride leg from the vehicle's position (`fromId` null, GTFS shape, `waitS` 0) is prepended; staying on the same
  trip merges into one ride leg. Sorted by arrival, deduped, max 6, departure = now, title starts with the line.
- Errors: 404 `vehicle not found`, 503 without live data, 422 with `via` / non-transit `travel`.
- Tests: `backend/tests/test_onboard.py`; `data/API.md` (with an example) and AGENTS.md updated.
