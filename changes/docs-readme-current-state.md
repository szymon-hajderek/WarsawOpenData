# docs/readme-current-state

- README rewritten for the current state: working status, the full feature list (Veturilo and own bike inside transit
  trips, live dock state / "Rowery na stacji", accessibility, planning from the vehicle, active trip, vehicle detection,
  live delays, map layers, 3D map, privacy-first extras), how the routing works (preprocessing: StationLocations,
  street graphs, stop-to-stop matrices, timetable; the adapted RAPTOR), evidence, known limitations.
- Environment setup: the router rebuilds stations / graphs / timetable by itself; matrices by hand (5-7 min per mode).
- Stale lines fixed in AGENTS.md (Python no longer plans transit) and frontend/README.md (street trips via POST /api/routes).
