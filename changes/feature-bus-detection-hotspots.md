# Changes on `feature/bus-detection-hotspots`

- `record_buses.py --trams`: records buses and trams (`data/live/vehicle_track_sample.json`, committed, 2026-10-18 05:04).
- `algorithms/simulation/hotspots.py` (+ `test_hotspots.py`): crowded 300 m cells, the part of a track near a place.
- `export_viz.py`: third page `artifacts/bus-detection/bus-detection-hotspots.html`: 10 most crowded places and the
  10 lines with the most GTFS trips that day, 5 points u * L each, results per group.
- Template: mini maps draw the exact point on the curve (u * L) and the GPS shift to the marker; place circle;
  texts for the hotspots page; table per group. All three pages rebuilt (numbers of the first two unchanged,
  the benchmark is measured again).
- RESULTS.md: third run.
- Assumptions: crowding counts only vehicles that moved at least 100 m (the 5 am recording put parked depots first);
  the ranking covers buses and trams together; the recording is from a quiet Sunday morning.
- Complexity sections on all result pages: `delay-statistics.html` (table + time of one `estimate`, measured in the
  simulation by `export_delay_viz.py`), `delay-docs.html` and `delay-tests.html` (test 10 "Czas obliczeń"),
  `veturilo-siting.html` (table + measured Dijkstra / greedy / hex build times from `siting_report.py --rebuild`).
  Bus detection pages: poll every 3 s and the delay buffer in memory.
