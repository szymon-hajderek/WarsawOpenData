# feature/bus-delay

Delay estimate for live buses and trams.

- `algorithms/bus_delay.py` (+ tests): buffer with midpoints (~5 s, none after a failed poll or a gap > 25 s),
  trip match by line + brigade + time window + shape, projection on the shape (loops: nearest the last projection),
  previous stop K-1, pass time within radius R, delay = pass time - scheduled departure at K-1 (can be negative).
- `backend/bus_detect.py`: per-vehicle delay buffer kept on the server (longest scheduled stop-to-stop time of the
  trip + 60 s, 10 min without a trip), new endpoint `GET /api/live/delay` (`data/API.md`).
- `backend/sources/mkuran.py`: `max_segment_for`, `brigade_trips` (trip stops + shape in epoch time, also
  yesterday's service for trips after midnight).
- GTFS `shape_dist_traveled` in `warsaw.zip` is in km and the cache truncates it to whole km, so the delay code computes
  distances along the shape in metres from coordinates and places each stop on the nearest shape point (in order).
- Trip match: a brigade drives the same shape many times a day, so among nearby trips the one whose timetable at the
  vehicle's position is closest to now wins.
- Frontend: `src/api/delay.ts` polls the confirmed vehicle every 10 s and sends a `bus-delay` window event
  (`BusDelayDetail`). No UI change; display is left to the UI work.
- `DELAY_RADIUS_M` env (default 30 m); `algorithms/simulation/tune_delay_radius.py` to pick it on live data,
  results in `algorithms/simulation/DELAY_RESULTS.md`.

Assumptions: the delay is compared with the scheduled departure; times are local Warsaw time (server in the same
time zone); a manual line (no vehicle) gets `available: false` with reason `unknown_vehicle`.
