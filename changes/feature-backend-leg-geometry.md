# feature/backend-leg-geometry

- New `backend/app/routing/geometry.py`: leg shapes for rendering only. `position()` (id -> `stations.json`
  position, null -> the query point), `leg_path()` per leg type: street = router path, transit = GTFS shape
  (`shape_slice`, then `shape_by_stops`; router legs get their calls from `trip_onward`), else a polyline
  through the named points with `approximatePath`. `_overlay` / `_loc` / `_pos` / `_ride_path` moved here.
- `legs_from_router()` is the one adapter for the current router answer and the agreed `/route` / `/plan` legs:
  ends as `{"id", "lonlat"}`, an id or `null`; no top-level totals needed (`_seconds()`, `_points()` read the
  legs); street, veturilo and transit legs. `points=(a, b)` stands for the `null` ends.
- `street_router.route()` returns the router answer unchanged (no `length_m` / `geometry` any more).
- Contract (`data/API.md`, `app/models.py`): `RouteLeg.elevators`, `RouteLeg.steps` (`[lat, lon]`, street legs),
  `RouteLeg.waitS` (transit: seconds at the boarding stop), `RouteLeg.tripId` (transit: GTFS trip id),
  `RouteOption.waitS` (transit waits + street waits). Real examples of a transit and a `travel=bike` answer.
- Today's transit legs get `waitS` = departure minus the arrival at the stop (access walk, transfer walk,
  Veturilo bridge) and `tripId`.
- Removed `GET /api/osm/route` (street-only trips = `POST /api/routes` with `travel`).
- Tests: `backend/tests/test_leg_geometry.py` (old vs new format, future transit / veturilo legs, `leg_path`,
  waits, `tripId`, `travel=bike` on the new format).
