# Delay estimate: choosing the radius R

How often does `estimate` (`algorithms/bus_delay.py`) find the delay, and how does the radius R change that?

## Method

`tune_delay_radius.py` polled the live ZTM bus feed (City Hall API) every 3 s for 8 minutes
(2026-10-17, about 18:52-19:00 Warsaw time, ~1100 buses; one poll failed with HTTP 500 and was treated as a break).
It keeps the same buffer as the server (midpoints, no midpoint after a failed poll or a gap > 25 s, per-trip length).
Every 60 s it ran `estimate` for every vehicle and every R: 8 evaluations, 8846 samples per R.
The first minutes include vehicles whose previous stop was passed before recording started, so the shares are a bit low.

Run from `backend/`: `uv run python ../algorithms/simulation/tune_delay_radius.py 8`.

## Results

| R (m) | samples | available | of samples with K-1 found | no trip | outside trip | no pass in R | median delay (s) | p10 / p90 (s) |
|---|---|---|---|---|---|---|---|---|
| 20 | 8846 | 78% | 86% | 324 | 500 | 1128 | 71 | -237 / 385 |
| 30 | 8846 | 81% | 89% | 324 | 500 | 860 | 70 | -240 / 385 |
| 50 | 8846 | 83% | 91% | 324 | 500 | 709 | 71 | -237 / 391 |
| 75 | 8846 | 84% | 92% | 324 | 500 | 628 | 71 | -240 / 394 |
| 100 | 8846 | 84% | 93% | 324 | 500 | 563 | 71 | -241 / 394 |

- "with K-1 found" = the trip matched and the vehicle is between two stops of it; the rest of those is "no pass in R".
- "no trip": no trip of that line + brigade runs now +- 15 min within 100 m of the vehicle.
- "outside trip": before the first stop or at the last one (layover at a terminus).

## Conclusion

- R = 30 m (default `DELAY_RADIUS_M`) gives the delay for 89% of vehicles between two stops. Going to 100 m adds only
  4 points but a point 100 m from the stop is about 10 s of driving away, so the time gets less exact. The delay
  distribution hardly changes with R.
- With points about every 5 s (midpoints) a moving bus is never more than ~25-35 m from the stop at its closest
  point, so 20 m already misses some passes; 30 m is the smallest radius that keeps the loss small.
- Typical delay in this sample: +70 s median, 10% of buses more than 4 min early, 10% more than 6.5 min late.

## Pitfall found while tuning

The first run gave only 31% at R = 30 m and R hardly mattered. The cause: `shape_dist_traveled` in `warsaw.zip`
is in km and the GTFS cache keeps whole units only, so stop K-1 was often wrong. The delay code now computes distances
along the shape in metres from coordinates (`mkuran._trip_static`).
