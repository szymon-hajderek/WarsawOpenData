# feature/bus-delay-simulation

Evidence for the delay estimate of `feature/bus-delay` (branched from it; PR #48 was not merged yet).

- `algorithms/simulation/record_delay_sample.py`: records 30 min of all live buses and trams from a local server plus
  the server's `/api/live/delay` answers for 6 lines (175, 180, 523, 189, 17, 33). Saved for future tests in
  `data/live/delay_sample.json.gz`.
- `algorithms/simulation/simulate_delay.py`: reference = moment the full recorded track crosses the stop on the trip
  shape; the replay feeds the same points to the server algorithm (buffer, midpoints, real failed polls, optional
  lost polls and GPS noise). `evaluate(sample, radius_m, drop, noise_m)` is reusable for a later search of the best R.
- `algorithms/simulation/export_delay_viz.py` + `artifacts/templates/delay-simulation.html` -> `artifacts/delay-simulation.html`
  (Polish report for a presentation). R stays 30 m.

- `algorithms/simulation/search_delay_radius.py` (+ tests): R search, 20..200 m every 10 m, then every 1 m between the two
  best neighbouring radii. `simulate_delay.evaluate_many` scores many radii in one replay.
- Results in `algorithms/simulation/DELAY_RESULTS.md`; report published privately at claude.ai as well.

Assumptions: the score of a radius = share of all passes shown with a delay within 30 s of the reference; ties go to the
smaller radius; live answers from the first 5 minutes are skipped (server buffer still filling); stops the algorithm never
had as K-1 (two stops passed between feed points) are left out of the accuracy numbers and counted separately.
