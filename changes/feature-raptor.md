# feature/raptor

RAPTOR transit routing in the C++ router: `POST /plan`.

- `backend/preprocess_transit.py` writes `data/derived/street/timetable.bin` (TTB1, writer in
  `algorithms/timetable_file.py`): every GTFS trip as calls at `stations.json` indexes, metro frequency runs expanded.
  `street_router.start()` rebuilds it when stale (~10 s).
- C++ (`algorithms/router/transit.hpp`, `matrix.hpp`, `raptor.hpp`, `main.cpp`): route patterns per service day
  (route + exact stop sequence, FIFO split, the previous day's trips after midnight), dense matrix footpaths per mode,
  Veturilo as an always-available dock-to-dock leg (walk mode only, 30 s + ride + 15 s), Pareto set (counted legs,
  arrival) + the street-only trip; street legs re-traced for the answer. `/health` gains `timetable` and `plan`.
- Answer format agreed with the router owner: ids only (no positions / shapes / names / RouteOption).
- `street_router.plan()` client (Warsaw service day, before 04:00 = previous day).
- Docs: `docs/raptor-graph.md` (the spec, as built), `algorithms/router/README.md` (`/plan`, timetable file),
  `data/API.md` (`/api/stations/health` fields), README setup, AGENTS.md.
- Tests: `algorithms/test_raptor.py` (brute force on 100 random toy timetables + named cases),
  `backend/tests/test_street_router_plan.py`.

Assumptions (decided during the work):
- Every limit is unlimited by default; footpaths read the whole dense matrix row (user's choice over a sparse cut).
- A journey with more legs is kept only when it arrives at least 1 s earlier (float ties are not options).
- A transit leg's `seconds` includes its `wait_s`, so an option's `seconds` is the sum of its legs.
- Accessible / stroller do not filter trips by `wheelchair_accessible`; GTFS pickup / drop-off types are ignored.
- `real_engine` is unchanged; a follow-up issue covers using `/plan` there, another the live data push.
