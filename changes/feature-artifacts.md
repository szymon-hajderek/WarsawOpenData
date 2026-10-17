# Changes on `feature/artifacts`

- New folder `artifacts/` for self-contained HTML pages, with `artifacts/README.md`.
- `artifacts/bus-detection-simulation.html`: results page of the nearest bus simulation (charts, mini maps, table).
- `artifacts/templates/bus-detection-simulation.html` + `algorithms/simulation/export_viz.py`: rebuild the page from
  `data/live/bus_track_sample.json` with the same seed as `simulate_nearest_buses.py`.
- `artifacts/bus-detection-fraction.html`: second run, point at u * L with u ~ U(0, 1), 10 points per line,
  hit rate by u. Both pages now explain how time is handled and show the complexity with a runtime benchmark.
- `simulate_nearest_buses.py`: new `time_at_fraction(tr, u)`; `random_time_on` uses it (same numbers as before).
- RESULTS.md: second run, time handling, complexity.
- AGENTS.md: folder, rebuild command, known time zone issue in `bus_detect._epoch` (not fixed here).
- Assumption: the recording time on the page comes from the feed (Warsaw time), not from the machine clock.
