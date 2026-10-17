# Integration tests: synthetic trips on real data

These tests run the whole backend (route engine, bus detection, delay, Veturilo, alerts, speed history) in
**simulation mode**. A synthetic user travels a planned route while a simulated clock moves. The phone's GPS
fixes, the live vehicle feed, Veturilo status and ZTM alerts all come from a scenario file, so a run gives
the same result every time and calls no external API.

## Run

From `backend/` (the first run builds the GTFS / OSM caches, then a full run takes about 6 minutes):

```bash
uv run pytest ../integration            # all
uv run pytest ../integration -m recorded  # only replays of recorded live data
uv run pytest ../integration -m gtfs      # only vehicles made from the GTFS timetable
```

Each run writes `integration/RESULTS.md` (metrics + checks per scenario) and `integration/report/results.json`
(the same plus user tracks and detections, for the replay page; git-ignored).

The normal unit tests (`uv run pytest tests ../algorithms`) do not collect this folder.

## Swap the route engine

**When a new pathfinding engine lands (the C++ `CppRouteEngine`), it MUST be tested by swapping the engine.**
Register it in `backend/app/routing/factory.py`, then run this whole suite with it and compare `RESULTS.md`
with a run of the current engine:

```bash
ROUTE_ENGINE=real uv run pytest ../integration && cp ../integration/RESULTS.md /tmp/RESULTS-real.md
```

```bash
ROUTE_ENGINE=cpp uv run pytest ../integration
```

Do not let the new engine replace `real` before this suite passes. The strict `xfail` cases in
`gtfs/test_engine_sanity.py` are bugs found in the current engine: a fixed engine turns them into `XPASS`
(a failure), so remove their `known_bug` field then.

## Two kinds of data

| Folder | Marker | Vehicles come from | Use |
|---|---|---|---|
| `recorded/` | `recorded` | a recording of the City Hall feed (`data/live/bus_track_sample.json`, 2 min) | does detection work on real, noisy data? |
| `gtfs/` | `gtfs` | the GTFS timetable and shapes (`backend/sim/synth.py`), with delays set by the test | whole trips, delays, Veturilo, alerts, history |

## Scenarios

| File | Test | What it checks |
|---|---|---|
| `recorded-bus-ride` | `recorded/test_bus_ride.py` | 30 users on real buses, GPS error 10/30/50 m: own bus in the top 4 / first |
| `trip-gorczewska-daszynskiego` | `gtfs/test_trip.py` | plan, walk, wait, ride, walk: arrival vs plan, ridden vehicle detected |
| `delay-wilenski-waszyngtona` | `gtfs/test_delay.py` | tram 4 min late: arrival moves, delay tag, user still catches it |
| `veturilo-kabaty-ursynow` | `gtfs/test_veturilo.py` | pickup station empty after 5 min: routes stop using it |
| `alert-wilenski-waszyngtona` | `gtfs/test_alert.py` | ZTM alert on the line after 2 min: "Zmiana na trasie" tag on exactly those options |
| `history-veturilo-ride` | `gtfs/test_history.py` | walk + bike track (a fix every 4 s) -> history API averages match the simulated speeds |
| `engine-sanity` | `gtfs/test_engine_sanity.py` | 8 trips: there are options, none leaves more than 60 min after the query |

## Scenario file (`scenarios/<name>.json`)

```json
{
 "title": "shown in RESULTS.md and the demo",
 "source": "gtfs",
 "start": "2026-10-21T08:00:00",
 "recording": "data/live/bus_track_sample.json",
 "trip": {"from": {"id": "a", "label": "A", "position": [52.23, 21.00]}, "to": {"...": "..."}, "profile": "standard"},
 "delays": [{"line": "10", "brigade": "4", "delay_s": 240}],
 "alerts": [{"from_s": 120, "lines": ["167"]}],
 "veturilo": [{"from_s": 300, "station_id": "123456", "bikes": 0}],
 "test": {"any": "values the test reads"}
}
```

- `source`: `recorded` (needs `recording`; the clock starts at its first poll unless `start` is set) or `gtfs`
  (needs `start`, Warsaw local time on a date the GTFS feed covers).
- `delays`, `alerts`, `veturilo` are optional; a test can also add them while it runs
  (`set_delay`, `add_alert`, `set_station` in `backend/sim/scenario.py`). `brigade: null` delays the whole line.
- `from_s` counts from `start`.

## How the synthetic user moves (`journey.py`)

- Walk and bike legs: along the leg geometry at the profile speed (`PROFILE_SPEED` in `real_engine.py`).
- Bus and tram legs: the user waits at the first point of the leg for a synthetic vehicle of the planned line
  whose trip reaches the end of the leg (within 150 m), rides it, and gets off within 80 m of the end.
  No such vehicle in 30 min = the trip fails.
- Metro and rail legs have no live feed: the user moves along the leg in its planned time, without waiting.
- GPS error drifts slowly (AR(1), `GpsNoise`), like a real receiver. Bus detection reads the feed every 10 s and
  the app sends the last 3 fixes (10 s apart) to `/api/live/nearest-buses`.

## Limits

- GTFS dates: a scenario date must be in `data/gtfs/warsaw.zip`. A new download drops old dates; then move
  the `start` dates of the `gtfs` scenarios.
- The recording is 2 minutes. A longer recording of buses, trams and Veturilo together is the next step.
- Every planned segment starts "now"; the tests do not wait at intermediate stops.
- A stale `data/derived/osm_graph.npz` from the old `Warsaw.osm.pbf` makes `osm.warm()` fail with an
  `IndexError`: delete it, it is rebuilt (issue #60).
- Train delays (`sources/realtime.py`) are empty in simulation mode; only buses and trams have a simulated feed.
- The engine changes which options it returns. When a scenario test fails with "no bus / tram option", first ask
  the engine for that trip; pick another trip if the engine now prefers metro or rail there.
