# fix/leg-ends-on-stations

- Transit leg paths (`backend/app/routing/geometry.py::_ride_path`) now start and end exactly at the mapped stop
  positions (`stations.json` / `GET /api/stations`): the GTFS shape slice is cut at the projections of the two mapped
  stops and joined to them. `shape_by_stops` (no stop distances) projects the mapped positions too.
- Before: the ride started / ended at its own GTFS shape points, median 11 m and up to 94 m (metro platforms) away
  from the stop markers and the walk legs. After: 0 m (walks: < 1 m, the router's 5-decimal rounding).
- Regression test `test_ride_path_starts_and_ends_at_the_mapped_stops`; `data/API.md` states the rule.
