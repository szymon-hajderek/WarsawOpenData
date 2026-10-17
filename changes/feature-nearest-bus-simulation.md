# Changes on `feature/nearest-bus-simulation`

- `algorithms/simulation/record_buses.py`: records live City Hall bus positions every 10 s for 2 min.
- `data/live/bus_track_sample.json`: one recorded sample (2026-10-17, ~880 buses), so results can be repeated.
- `algorithms/simulation/simulate_nearest_buses.py`: simulated users on bus polylines, GPS radius 10/25/50/100 m,
  1 and 3 points; checks top-1 / top-4 of `rank_buses`.
- `algorithms/simulation/RESULTS.md`: method, results, limits.
- Assumptions: 15 lines x 5 points, fixed seed 42; the sample is committed (1.7 MB).
