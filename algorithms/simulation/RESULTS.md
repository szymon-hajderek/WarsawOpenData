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

## Second run: point at u * L, u ~ U(0, 1)

Same recording and the same 15 lines, but each point is drawn explicitly: u from U(0, 1), the point lies at
distance u * L from the start of the polyline (L = its length). This is the same distribution as above
(uniform by length), now with 10 points per line = 150 trials per row and u stored for every trial
(`export_viz.py`, seeds 2026 for u and 2027 for the radius).

| radius | points | top-1 | in popup (top-4) | right line in top-4 | median RMSE to own bus |
|---|---|---|---|---|---|
| 10 m | 1 | 85% | 100% | 100% | 49 m |
| 10 m | 3 | 97% | 100% | 100% | 34 m |
| 25 m | 1 | 83% | 100% | 100% | 46 m |
| 25 m | 3 | 97% | 100% | 100% | 40 m |
| 50 m | 1 | 86% | 100% | 100% | 52 m |
| 50 m | 3 | 97% | 100% | 100% | 48 m |
| 100 m | 1 | 81% | 100% | 100% | 84 m |
| 100 m | 3 | 96% | 100% | 100% | 78 m |

- The numbers agree with the first run: the own bus is always in the popup; top-1 is 96-97% with 3 points
  and 81-86% with 1 point.
- By u (all radii, 3 points): 100 / 99 / 99 / 100 / 89% for u in 0-0.2 ... 0.8-1.0. The drop at the end comes
  almost only from line 131 (13 of 15 misses), so it is about that route, not about the end of a polyline.

## Third run: hard cases (crowded places, frequent lines, buses and trams)

New recording with buses and trams: `record_buses.py --trams` -> `data/live/vehicle_track_sample.json`
(2026-10-18, Sunday 05:04 Warsaw time, 773 vehicles of which 139 trams). The ranking covers all of them.

- **10 most crowded places**: 300 m cells with the most vehicles at the same moment (one poll), at least 600 m apart,
  counting only vehicles that moved at least 100 m in the recording (at 5 am the raw count was led by depots full
  of parked buses). Per place one vehicle that passed through it; 5 points u * L on the part of its track within
  300 m of the cell centre. Places: R-3 Zajezdnia Ostrobramska (7 vehicles at once), Dw. Centralny (6),
  Metro Młociny, Maklakiewicza, Pl. Zbawiciela (5 each), Cybernetyki, Dw. Wileński, Metro Stadion Narodowy,
  R-4 Zajezdnia Stalowa, Kwatery Głównej (4 each).
- **10 most frequent lines**: most GTFS trips that day: trams 9, 17, 16, 1, 2 and buses 189, 184, 523, 190, 509
  (197-272 trips). One moving vehicle per line, 5 points u * L on its whole track.
- 50 + 50 trials per row, seeds 1018 (choice + u) and 1019 (radius).

| group | radius | points | top-1 | in popup (top-4) | median RMSE |
|---|---|---|---|---|---|
| places | 10 m | 1 | 70% | 98% | 27 m |
| places | 10 m | 3 | 94% | 100% | 22 m |
| places | 25 m | 1 | 70% | 98% | 34 m |
| places | 25 m | 3 | 92% | 100% | 29 m |
| places | 50 m | 1 | 66% | 94% | 52 m |
| places | 50 m | 3 | 86% | 100% | 39 m |
| places | 100 m | 1 | 52% | 92% | 78 m |
| places | 100 m | 3 | 78% | 100% | 74 m |
| lines | 10 m | 1 | 94% | 100% | 41 m |
| lines | 10 m | 3 | 98% | 100% | 31 m |
| lines | 25 m | 1 | 94% | 100% | 42 m |
| lines | 25 m | 3 | 98% | 100% | 35 m |
| lines | 50 m | 1 | 94% | 100% | 46 m |
| lines | 50 m | 3 | 98% | 100% | 45 m |
| lines | 100 m | 1 | 90% | 100% | 84 m |
| lines | 100 m | 3 | 98% | 100% | 80 m |

- Crowded places are the hard case: with 1 point the first suggestion is right in only 52-70% of trials, and with a
  large GPS error the own vehicle can drop out of the popup (92-98% in top-4). 3 points fix the popup (100%) and
  lift top-1 to 78-94%.
- Frequent lines behave like the earlier runs (top-1 90-98%, always in the popup).
- Limit: one 2-minute window early on a Sunday morning, so streets were emptier than at rush hour. Record again at
  a peak hour (one command) to check the numbers under real crowding.

## How time is handled

1. Bus reports keep the feed time t_i (Warsaw time). Repeated reports of the cached feed are removed.
2. A point on the polyline gets its time t_p by linear interpolation between the two reports around it.
3. User track: 1 point at t_p, or 3 points at t_p - 20 s, t_p - 10 s, t_p (the app samples every 10 s).
   Positions come from the polyline (clamped to the first report), then move inside radius R.
4. The algorithm sees, for every bus, only reports with t <= t_p, the last 3 (like `backend/bus_detect.py`).
5. Each user point is paired with the bus report closest in time; MSE = mean squared haversine distance.
6. The last report is 0-20 s older than t_p, so even at R = 10 m the RMSE to the own bus is about 40 m.

## Complexity

- `rank_buses` per request: O(V * K * H + V log V); V buses (~880), K user points (<= 3), H reports per bus (3).
  About 8k distances; measured median ~2 ms on the dev laptop. Linear in V: 0.6 ms at 250 buses, 22.5 ms at 8000.
- Poller: O(V) per 10 s; memory O(V * H).
- One simulation trial: O(V * T) to build the backend view (T <= 13 reports per bus) + the ranking.
- The full sort can be replaced by `heapq.nsmallest(4, ...)`: O(V log 4).

## Limits

- One 2-minute window at one time of day; 15 lines, 75 trials per row.
- The simulated user is always inside a bus. Users who stand at a stop or walk next to a street
  (false positives) are not tested.
- Points lie exactly on the line between two reports; real streets curve between reports.
