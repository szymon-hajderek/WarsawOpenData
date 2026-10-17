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

## Simulation against the full track (recording of 2026-10-17)

`record_delay_sample.py` recorded 32 minutes on a local server (2026-10-17, 19:40-20:12 Warsaw time, 1097 buses and
trams, ~176 000 feed points, no failed polls) plus the server's own `/api/live/delay` answers every 30 s for lines
175, 180, 523, 189 (bus) and 17, 33 (tram). Data: `data/live/delay_sample.json.gz`.
Reference = the moment the full track crosses the stop on the trip shape. `simulate_delay.py` replays the same points
as the server sees them. 1130 passes by a stop on these 6 lines (22 more were skipped: two stops passed between feed points).

| setting (R = 30 m) | available | median abs error | p90 abs error | error <= 30 s (of shown) | score |
|---|---|---|---|---|---|
| data as recorded | 98.2% | 2 s | 14 s | 96.8% | 95.0% |
| 10% polls lost | 96.7% | 2 s | 15 s | 96.8% | 93.6% |
| 30% polls lost | 91.4% | 3 s | 18 s | 96.6% | 88.2% |
| GPS noise 10 m | 97.9% | 2.5 s | 14 s | 96.8% | 94.8% |
| GPS noise 20 m | 97.8% | 4 s | 18 s | 96.3% | 94.2% |

Live server answers (after a 5 min warm-up), against the same reference: 599 passes, 98.2% available, median abs
error 2 s, p90 13 s, 98.6% within 30 s.

## Search for the best R (`search_delay_radius.py`)

Score = share of all passes shown with a delay within 30 s of the reference. Coarse R = 20..200 m every 10 m, then every
1 m between the two best neighbours.

| R (m) | 20 | 30 | 40 | 50 | 60 | 70 | 80 .. 200 |
|---|---|---|---|---|---|---|---|
| score | 93.3% | 95.0% | 95.8% | 96.3% | 96.3% | 96.4% | 96.5% |
| available | 96.3% | 98.2% | 98.9% | 99.6% | 99.6% | 99.8% | 100% |

Best neighbours 80 and 90 m; every 1 m between them gives the same score, so the smallest wins: **R = 80 m** (96.5%).
The curve is flat from 80 m: the estimate always uses the buffered point closest to the stop, so R only decides whether
to show it. A bigger R does not make shown delays worse in this recording; it only adds the few passes whose closest
point was 30-80 m away. The default stays 30 m (`DELAY_RADIUS_M`) until the team decides; the gain would be +1.5 points.

Limits: reference and estimate use the same feed points, so this measures the method, not the GPS error of the feed;
one evening, 6 lines.
