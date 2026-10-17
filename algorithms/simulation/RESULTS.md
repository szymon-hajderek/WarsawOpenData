# Nearest bus detection: simulation results

How well does `rank_buses` (`algorithms/nearest_buses.py`) find the bus a user is riding?

## Method

1. `record_buses.py` recorded live ZTM bus positions from the City Hall API every 10 s for 2 minutes
   (2026-10-17, about 17:25 Warsaw time, ~870 fresh buses per poll). Sample: `data/live/bus_track_sample.json`.
2. `simulate_nearest_buses.py` builds a polyline per vehicle from its reports and picks 15 random lines
   (one moving vehicle each: at least 5 reports and 300 m), 5 random points per line = 75 trials per row.
3. The simulated user is at that point (1 point) or has ridden the bus for the last 20 s (3 points, 10 s apart).
   Each user point is moved to a uniform random spot inside a circle of radius R (GPS error).
4. The algorithm only sees what the backend would have at that moment: the last 3 reports per vehicle that
   are not newer than the user's time, for all ~880 buses.

Run from `backend/`: `uv run python ../algorithms/simulation/simulate_nearest_buses.py` (fixed seed 42).

## Results

| radius | points | top-1 | in popup (top-4) | right line in top-4 | median RMSE to own bus |
|---|---|---|---|---|---|
| 10 m | 1 | 88% | 100% | 100% | 45 m |
| 10 m | 3 | 100% | 100% | 100% | 37 m |
| 25 m | 1 | 85% | 100% | 100% | 51 m |
| 25 m | 3 | 100% | 100% | 100% | 38 m |
| 50 m | 1 | 89% | 100% | 100% | 55 m |
| 50 m | 3 | 99% | 100% | 100% | 48 m |
| 100 m | 1 | 80% | 100% | 100% | 84 m |
| 100 m | 3 | 96% | 100% | 100% | 80 m |

- The user's bus is always in the popup (top-4), even with 100 m GPS error.
- 3 points beat 1 point clearly: the first suggestion is right in 96-100% of trials vs 80-89%.
  The automatic popup at start uses 1 point, so its first suggestion is wrong about 1 time in 8;
  the manual re-check (`requestLinePopup()`, 1-3 points) is better.
- Even with a small radius the RMSE to the own bus is ~40 m: the backend knows only the last report,
  and the bus has moved since then (reports come every ~10-20 s). Moving the bus forward to the user's
  time (speed from its last two reports) should lower it.

## Limits

- One 2-minute window at one time of day; 15 lines, 75 trials per row.
- The simulated user is always inside a bus. Users who stand at a stop or walk next to a street
  (false positives) are not tested.
- Points lie exactly on the line between two reports; real streets curve between reports.
