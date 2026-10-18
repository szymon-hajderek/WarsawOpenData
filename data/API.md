# API

This file is the **contract** of the backend API (FastAPI, `backend/`). Frontend and backend code must match it.
To change the API, edit this file first, then the code, in the same PR (see `AGENTS.md`).

- Base URL in development: `http://localhost:8000`. One app serves everything below:
  `cd backend && uv run uvicorn main:app --reload`. `app.main:app` is the old slim app (routes, geocode, speed history,
  journeys and `GET /health` only); do not run both on port 8000.
- Interactive docs generated from the code: `/docs`, schema: `/openapi.json`.
- All answers are JSON. Errors have the form `{"detail": "<message>"}`.
- Errors that any endpoint can return (they are not repeated below):
  - `422` for a query value that is out of range or in the wrong form (e.g. `limit=-1`, `lat=999`, `bbox=1,2`).
  - `502 {"detail": "external data source failed, try again later"}` when an external API (City Hall, Nextbike)
    fails. The message never contains the URL or a key.
  - `503` when a key in the server `.env` is empty (the message names it), or, for `/api/gtfs`, `/api/osm`,
    `/api/routes`, `/api/live/nearest-buses` and `/api/veturilo/siting`, while the server loads its caches and starts
    the street router (about 1-2 minutes after a start, longer on the first run). The header `Retry-After: 30` is set.
    Also `503` when the C++ street router does not answer (`{"detail": "street router not reachable at ..."}`).
  - `404` when a data file is missing on the server (run `download.py`, or `report.py` for `/api/stats`).
- Users never call external APIs. Only the server does, and it caches the answers.
- No authentication on our side. The keys for City Hall endpoints live in `.env` on the server (`ACCESS.md`).
- Examples below are real answers from a running server. Long lists are cut to 1-2 items and end with `"..."`.
- Coordinates are WGS84 `lat` / `lon` in degrees. Times are Warsaw local time.
- Endpoint groups are listed below, plus 6 simulation endpoints that exist only in simulation mode (`SIM_SCENARIO`).

| Group | Prefix | Source file |
|---|---|---|
| [Meta](#meta) | `/api` | `backend/main.py` |
| [GTFS](#gtfs-timetables-and-stops) | `/api/gtfs` | `backend/sources/mkuran.py` |
| [Live vehicles](#live-vehicles-and-city-hall) | `/api/live`, `/api/ztm` | `backend/sources/um_warszawa.py` |
| [Bus detection](#bus-detection) | `/api/live` | `backend/bus_detect.py` |
| [Veturilo](#veturilo-city-bikes) | `/api/veturilo` | `backend/sources/nextbike.py`, `backend/sources/siting.py` (`/siting`) |
| [OSM](#osm-street-graph) | `/api/osm` | `backend/sources/osm.py` |
| [Stations](#stations-stationlocations) | `/api/stations` | `backend/api_stations.py` |
| [Routing](#routing) | `/api/routes`, `/api/geocode`, `/health` (slim app only) | `backend/app/` |
| [Speed history](#speed-history) | `/api/history` | `backend/app/api/history.py` |
| [Journey statistics](#journey-statistics) | `/api/journeys` | `backend/app/api/journeys.py` |
| [Simulation](#simulation-only-with-sim_scenario) | `/api/sim` | `backend/sim/api.py` |

## IDs

- Stop ids carry a feed prefix: `ztm:700901`, `wkd:brzoz`, `pkp:33605_RAIL_1_5`.
  ZTM `700901` = group `7009` + post `01`. A PKP rail platform is `pkp:<station>_P<n>` (`pkp:33506_P2`); the GTFS
  platform + track children (`pkp:33506_RAIL_2_20`) fold into it.
- Route ids: `ztm:131`. Group ids: `ztm:7009`. Veturilo station: `station_id` (`203610`), global id `vet:203610`.
- `line` in live endpoints = GTFS `route_short_name`; `route_id` = `ztm:<line>`.
- Veturilo and OSM have no shared ids with GTFS: join them by distance.
- Geocoded places use OSM object references: `osm:node:123`, `osm:way:123` or `osm:relation:123`.
  The former `osm-<place_id>` was a Nominatim database key, not a durable object reference.

---

## Meta

### `GET /api/sources`

All data sources: URL, local file, key, license, status.

Answer: list of objects with `id`, `module`, `status`, `file`, `url`, `key`, `content`, `license`, `attribution`.

```json
[
 {
  "id": "mkuran_ztm", "module": "mkuran", "status": "downloaded",
  "file": "data/gtfs/warsaw.zip", "url": "https://mkuran.pl/gtfs/warsaw.zip", "key": null,
  "content": "GTFS: ZTM bus, tram, metro, SKM stops (posts) + timetables + shapes",
  "license": "ZTM Warszawa data terms; ODbL for bus shapes",
  "attribution": "ZTM Warszawa, Mikołaj Kuranowski, OpenStreetMap contributors (attributions.txt)"
 },
 "..."
]
```

### `GET /api/stats`

Counts from the last `uv run python report.py` run (the file `data/report.json`).

Top-level keys: `generated`, `reference_date`, `vertices`, `item1_transit_edges`, `item2_walk_pairs`,
`item3_osm`, `item4_feasibility`, `compatibility`, `street_matrix`, `stations`, `seconds_to_build`, `endpoints`.

```json
{
 "generated": "2026-10-18T00:51:21",
 "reference_date": "20261021",
 "vertices": {"transit_posts": 7193, "transit_stop_groups": 3047, "veturilo_stations": 349,
              "osm_walk": 1792617, "osm_bike": 1222025, "...": "..."},
 "...": "..."
}
```

---

## GTFS (timetables and stops)

Data from the `mkuran.pl` GTFS feeds: ZTM (bus, tram, metro, SKM), WKD and other trains.

### `GET /api/gtfs/stops`

Boarding points (posts / platforms). Merged rail duplicates are hidden unless `include_merged=true`.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | all | `bus`, `tram`, `metro` or `rail` |
| `feed` | string | all | `ztm`, `wkd` or `pkp` |
| `bbox` | string | ZTM area | `min_lat,min_lon,max_lat,max_lon` (four numbers, min <= max, else `422`) |
| `include_merged` | bool | `false` | also return stops merged into another station |

Answer: list of stops. Fields: `id`, `feed`, `raw_id`, `name`, `code`, `lat`, `lon`, `location_type`,
`parent`, `wheelchair` (`"0"` unknown, `"1"` yes, `"2"` no), `zone` (`"1"`, `"2"` or `"1+2"`),
`group`, `modes` (list), `served` (bool),
`same_as` (id of the station this stop is merged into, or `null`), `platform` (id of the rail platform this GTFS
child folds into, or `null`), `members` (ids folded into this platform / station; `[]` for a post),
`boarding` (bool: a place where a trip is boarded; only these are listed unless `include_merged=true`).

```json
[
 {"id": "ztm:100101", "feed": "ztm", "raw_id": "100101", "name": "Kijowska", "code": "01",
  "lat": 52.248455, "lon": 21.044827, "location_type": 0, "parent": null, "wheelchair": "1",
  "zone": "1", "group": "ztm:1001", "modes": ["bus"], "served": true, "same_as": null,
  "platform": null, "members": [], "boarding": true},
 "..."
]
```

### `GET /api/gtfs/stops/{stop_id}`

One stop. Same fields as above. `404` for an unknown id.

```json
{"id": "ztm:700901", "feed": "ztm", "raw_id": "700901", "name": "Marszałkowska", "code": "01",
 "lat": 52.217931, "lon": 21.020112, "location_type": 0, "parent": null, "wheelchair": "2",
 "zone": "1", "group": "ztm:7009", "modes": ["bus"], "served": true, "same_as": null,
 "platform": null, "members": [], "boarding": true}
```

A rail platform (`GET /api/gtfs/stops/pkp:33506_P2`):

```json
{"id": "pkp:33506_P2", "feed": "pkp", "raw_id": "33506_P2", "name": "Warszawa Zachodnia", "code": "peron 2",
 "lat": 52.219607493945006, "lon": 20.965480058045, "location_type": 0, "parent": "pkp:33506", "wheelchair": "1",
 "zone": "", "group": "pkp:33506", "modes": ["rail"], "served": true, "same_as": null, "platform": null,
 "members": ["pkp:33506_RAIL_2_20", "pkp:33506_RAIL_2_22"], "boarding": true}
```

Error: `404 {"detail": "unknown stop_id (use the feed prefix, e.g. ztm:700901)"}`.

### `GET /api/gtfs/stop-groups`

Stop groups (ZTM group, station parent) with their posts.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `feed` | string | all | `ztm`, `wkd` or `pkp` |

```json
[{"group": "ztm:1001", "name": "Kijowska", "posts": ["ztm:100101", "ztm:100102", "..."]}, "..."]
```

### `GET /api/gtfs/routes`

Lines from all GTFS feeds.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | all | `bus`, `tram`, `metro`, `rail` |
| `feed` | string | all | `ztm`, `wkd`, `pkp` |

```json
[{"id": "ztm:1", "feed": "ztm", "short_name": "1", "long_name": "Annopol – P+R Al. Krakowska",
  "agency": "0", "type": 0, "mode": "tram", "color": "B60000"}, "..."]
```

### `GET /api/gtfs/routes/{route_id}/stops`

Distinct stop sequences (variants) of one line. `variants` is a list of lists of stop ids.

```json
{"route": {"id": "ztm:131", "feed": "ztm", "short_name": "131", "long_name": "Wilanów – Dw. Centralny",
           "agency": "0", "type": 3, "mode": "bus", "color": "880077"},
 "variants": [["ztm:700221", "ztm:701315", "..."], "..."]}
```

Error: `404 {"detail": "unknown route_id (use the feed prefix, e.g. ztm:131)"}`.

### `GET /api/gtfs/stops/{stop_id}/departures`

Next departures from a stop. A merged rail station also lists the trains of the platforms merged into it.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `date` | string `YYYYMMDD` | today | service day |
| `time` | string `HH:MM` | now | earliest departure |
| `limit` | int `1-200` | `20` | maximum number of rows |

```json
[{"time": "15:47:00", "sec": 56820, "line": "182", "mode": "bus", "route_id": "ztm:182",
  "trip_id": "ztm:2026-10-17:182:SbS:621:1535", "brigade": "621",
  "headsign": "Okęcie", "wheelchair": "1", "feed": "ztm"}, "..."]
```

Errors: `404 {"detail": "unknown stop_id"}`; `422` for a `date` or `time` in the wrong form.

### `GET /api/gtfs/edges`

Unique "stop to next stop" edges per route (canonical stop ids). For building a transit graph.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `limit` | int `1-10000` | `1000` | page size |
| `offset` | int `>= 0` | `0` | first item |

```json
{"total": 22611, "items": [{"from": "ztm:100101", "to": "ztm:200101", "route": "ztm:123"}, "..."]}
```

### `GET /api/gtfs/merge`

Rail stations merged across feeds (distance < 150 m, same name) and near misses.

```json
{"merged": {"wkd:walje": "ztm:4913", "pkp:119206": "ztm:1930", "...": "..."},
 "unmatched_near": [{"stop": "wkd:prpkp_bus", "name": "PKP Pruszków", "ztm": "ztm:4905",
                     "ztm_name": "Pruszków", "distance_m": 97}]}
```

---

## Live vehicles and City Hall

Data from `api.um.warszawa.pl`. These endpoints need `PORTAL_KEY` / `WAW_API_KEY` in `.env` on the server.
Answers are cached for 30 s, except `GET /api/live/vehicles` (3 s).

### `GET /api/live/vehicles`

Live ZTM bus or tram positions.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `type` | string | `bus` | `bus` or `tram` |
| `line` | string, up to 10 chars | all | keep one line only |
| `max_age_s` | int `1-86400` | `300` | drop positions older than this (the feed holds old positions) |

```json
[{"line": "161", "brigade": "2", "lat": 52.163409, "lon": 21.208935, "time": "2026-10-17 15:47:36",
  "vehicle": "1000", "mode": "bus", "route_id": "ztm:161"}, "..."]
```

Error: `400 {"detail": "type must be bus or tram"}`.
`503 {"detail": "PORTAL_KEY is not set"}` when `.env` has no key.
`503 {"detail": "live vehicle feed is unavailable"}` when the City Hall feed returns an error.

### `GET /api/ztm/stops/{stop_id}/lines`

Lines that stop at one ZTM post. `stop_id` is `ztm:700901` or `700901`. Only ZTM bus and tram posts work.

```json
["151", "143", "182", "525", "520", "187", "523", "188", "138", "502", "514", "N25"]
```

Error: `400 {"detail": "only ZTM bus / tram posts have a City Hall id (e.g. ztm:700901)"}`.

### `GET /api/ztm/stops/{stop_id}/lines/{line}/times`

Planned times of one line at one ZTM post for today.

```json
[{"time": "18:17:00", "brigade": "M4", "direction": "Rechniewskiego", "variant": "TP-REH"}, "..."]
```

Error: `400` as above.

### `GET /api/ztm/routes/{line}`

Official route variants of a line, with GTFS stop ids and distances (snapshot file, not live).
Answer: object keyed by variant code. Each value is the list of stops in order.

```json
{"TD-0REH": [{"order": 0, "stop_id": "ztm:R-1000", "distance_m": 0, "type": "6"},
             {"order": 1, "stop_id": "ztm:250202", "distance_m": 2488, "type": "3"}, "..."],
 "...": "..."}
```

Error: `404 {"detail": "unknown line"}`.

---

## Bus detection

Answers "which vehicle is the user on?". The server polls live bus and tram positions every 3 s and keeps
the last 3 positions of each vehicle. It ranks them by the error against the last 1-3 user positions
(`algorithms/nearest_buses.py`). `direction` is the GTFS headsign of the trip with the same line and brigade.

### `POST /api/live/nearest-buses`

Body (JSON):

| Field | Type | Meaning |
|---|---|---|
| `points` | list, at least 1 | user positions, oldest first; the server uses the last 3 |
| `points[].lat`, `points[].lon` | number | position |
| `points[].time_ms` | number | Unix time in milliseconds |

Answer:

| Field | Meaning |
|---|---|
| `candidates` | up to 4 vehicles, lowest error first: `id`, `vehicle`, `line`, `brigade`, `mode` (`"bus"` or `"tram"`), `direction` (GTFS headsign, empty when no trip matches), `rmse_m` |
| `lines` | all lines seen in the live feed, sorted |
| `updated_at` | Unix time (seconds) of the last poll |

```json
{"candidates": [{"id": "bus-5914", "vehicle": "5914", "line": "175", "brigade": "405",
                 "mode": "bus", "direction": "Lotnisko Chopina", "rmse_m": 54.3}, "..."],
 "lines": ["102", "103", "104", "..."],
 "updated_at": 1760712345.6}
```

Errors: `400 {"detail": "send at least one point"}`; `503` when there is no live vehicle data yet. The server forgets a vehicle that has not reported for 5 minutes.

### `GET /api/live/delay`

Estimated delay of one live bus or tram (`algorithms/bus_delay.py`). The server buffers each vehicle's positions
for the longest scheduled time between two stops of its trip (+ 60 s; 10 min when no trip matches), with an extra
point in the middle of every two feed points (about every 5 s) when no poll failed between them and they are at most
25 s apart. The vehicle's position is projected on the GTFS shape of its trip (same line + brigade, running now ± 15 min,
shape closer than 100 m; of those, the trip whose timetable at that point is closest to now); the last stop passed is K-1, the next one K. Delay = time the vehicle was closest to K-1
(within `DELAY_RADIUS_M`, default 30 m) - scheduled departure at K-1. It is shown as the expected delay at K.

| Query | Type | Meaning |
|---|---|---|
| `vehicle` | string | vehicle id as in `nearest-buses` candidates, e.g. `bus-5914`, `tram-3120` |

Answer:

| Field | Meaning |
|---|---|
| `vehicleId`, `vehicle`, `line`, `brigade`, `mode` | the vehicle |
| `tripId`, `headsign` | matched GTFS trip, `null` when none matches |
| `available` | `false` = "delay data unavailable" |
| `reason` | `null` when available, else `no_trip`, `outside_trip` (before the first / at the last stop) or `no_pass_in_radius` |
| `delaySec` | seconds, negative = early; `null` when not available |
| `prevStop` | stop K-1: `id`, `name`, `scheduled` (`HH:MM:SS`), `passedAt` (`HH:MM:SS` or `null`); `null` when unknown |
| `nextStop` | stop K: `id`, `name`, `scheduled`, `expected` (scheduled + delay, `null` when not available); `null` when unknown |
| `radiusM` | radius used |
| `updatedAt` | Unix time (seconds) of the last poll |

```json
{"vehicleId": "bus-2246", "vehicle": "2246", "line": "517", "brigade": "3", "mode": "bus",
 "tripId": "ztm:2026-10-17:517:SbS:3:1853", "headsign": "Ursus-Niedźwiadek", "available": true, "reason": null,
 "delaySec": 8,
 "prevStop": {"id": "ztm:703302", "name": "Krucza", "scheduled": "18:57:00", "passedAt": "18:57:08"},
 "nextStop": {"id": "ztm:701306", "name": "Centrum", "scheduled": "18:59:00", "expected": "18:59:08"},
 "radiusM": 30.0, "updatedAt": 1792249203.8}
```

Not available (the vehicle passed K-1 but no buffered point was within the radius):

```json
{"vehicleId": "bus-1862", "vehicle": "1862", "line": "117", "brigade": "1", "mode": "bus",
 "tripId": "ztm:2026-10-17:117:SbS:1:1832", "headsign": "Dw. Centralny", "available": false,
 "reason": "no_pass_in_radius", "delaySec": null,
 "prevStop": {"id": "ztm:703302", "name": "Krucza", "scheduled": "18:55:00", "passedAt": null},
 "nextStop": {"id": "ztm:701306", "name": "Centrum", "scheduled": "18:57:00", "expected": null},
 "radiusM": 30.0, "updatedAt": 1792249203.8}
```

Errors: `404 {"detail": "unknown vehicle"}`; `503` when there is no live vehicle data yet.

---

## Veturilo (city bikes)

Nextbike GBFS feed. Stations come from a saved file; status and bikes are live (30 s cache).

### `GET /api/veturilo/stations`

```json
[{"id": "vet:203610", "station_id": "203610", "name": "Koneser", "number": "6419",
  "lat": 52.25602, "lon": 21.046219, "capacity": 10, "virtual": false}, "..."]
```

### `GET /api/veturilo/stations/{station_id}`

One station plus its live status in `status`. `404 {"detail": "unknown station_id"}` for an unknown id.

```json
{"id": "vet:203610", "station_id": "203610", "name": "Koneser", "number": "6419",
 "lat": 52.25602, "lon": 21.046219, "capacity": 10, "virtual": false,
 "status": {"station_id": "203610", "bikes": 21, "docks": 0,
            "types": [{"vehicle_type_id": "71", "count": 19}, "..."],
            "renting": true, "returning": true}}
```

### `GET /api/veturilo/status`

Live bikes and free docks per station.

```json
[{"station_id": "203610", "bikes": 21, "docks": 0,
  "types": [{"vehicle_type_id": "71", "count": 19}, "..."], "renting": true, "returning": true}, "..."]
```

### `GET /api/veturilo/free-bikes`

Live list of bikes, at stations and parked outside them (`station_id` is set only at a station).

```json
[{"bike_id": "A18jGZv7W6MAxmaIa8yGJ46zV0l2Y5JM", "is_reserved": false, "is_disabled": false,
  "rental_uris": {"android": "https://app.nextbike.net/station?id=203610",
                  "ios": "https://app.nextbike.net/station?id=203610",
                  "web": "https://nxtb.it/p/203610"},
  "lat": 52.25602, "lon": 21.046219, "vehicle_type_id": "71", "station_id": "203610"}, "..."]
```

### `GET /api/veturilo/vehicle-types`

Bike types (classic, e-bike, ...). Match `vehicle_type_id` from the endpoints above.

```json
[{"vehicle_type_id": "71", "vehicle_image": "https://static.nextbike.net/app/biketypes-v5/type/vw/71/h500.png",
  "name": "Rower standardowy", "_description": "", "form_factor": "bicycle",
  "rider_capacity": 1, "propulsion_type": "human"}, "..."]
```

### `GET /api/veturilo/siting`

Best hexes for **new** Veturilo stations, picked one by one (`backend/sources/siting.py`,
`algorithms/station_siting.py`). Warsaw is split into hexagons (radius 175 m); each gets
`J = -alpha*T*(1 + delta*E) + beta*P(dNet) + gamma*S`, `P(d) = (1 - d/r)^2` for `d < r`, else 0. Lowest `J` wins;
then a station is placed there and `dNet` is updated before the next pick. **`t` and `e` come from MOCK data**
(`data/mock/`). Hexes that already have a station or have no street are never proposed.

| Parameter | Default | Meaning |
|---|---|---|
| `n` | 10 | number of proposals, 1..50 |
| `alpha` | 1 | weight of car traffic `T`, 0..100 |
| `beta` | 1 | weight of the penalty `P` for being near a station, 0..100 |
| `gamma` | 0.5 | weight of the safety value `S`, 0..100 |
| `delta` | 0.5 | how much e-scooters `E` boost `T`, 0..100 |
| `r` | 1000 | penalty radius `R` in metres, 50..5000 |

Answer fields: `rank`, `hex` (axial `q:r`), `lat`, `lon` (hex centre), `j`, `t` (0..1), `e` (0..1), `dNet` (bike-network
metres to the nearest station at the moment of the pick, `null` = more than 5000 m), `p`, `s` (0 = bike path, 1 = multi-lane
road without one). Out-of-range parameter -> 422. While the hex grid is built at server start -> 503.

```json
[{"rank": 1, "hex": "-6331:22123", "lat": 52.226191, "lon": 21.053264, "j": -1.1654, "t": 1.0, "e": 0.7389,
  "dNet": 1241.4, "p": 0.0, "s": 0.4082},
 {"rank": 2, "hex": "-6352:22121", "lat": 52.22147, "lon": 20.955353, "j": -1.1533, "t": 1.0, "e": 0.6526,
  "dNet": 848.4, "p": 0.023, "s": 0.3}]
```

---

## Stations (StationLocations)

The one list of transport nodes (bus / tram posts, metro platforms, rail platforms and stations, Veturilo) shared
by the C++ street router, the backend and the frontend. GTFS decides what exists; where an exact OSM match exists
(post `ref` = ZTM stop id within 50 m, rail platform number within 50 m) the position is the OSM object, else GTFS.
Ids are the mkuran ids (`ztm:435102`, `ztm:7014M:P1`, `pkp:33506_P2`, `wkd:brzoz`, `vet:203610`) and the router
accepts them as `from` / `to`. Built at server start into `data/derived/stations.json`; requests never read raw
data. Rules and record fields: `algorithms/router/README.md` ("StationLocations").

### `GET /api/stations`

| Query | Type | Default | Meaning |
|---|---|---|---|
| `kind` | string | all | `bus_post`, `tram_post`, `metro_platform`, `rail_platform`, `rail_station`, `veturilo` (else `422`) |
| `feed` | string | all | `ztm`, `pkp`, `wkd`, `nextbike` |
| `source` | string | all | `osm` or `gtfs` (where the position comes from) |
| `bbox` | string | ZTM area | `min_lat,min_lon,max_lat,max_lon` |

Answer: list of locations. Fields: `id`, `kind`, `name`, `code`, `modes`, `feed`, `position` (`{lat, lon}`, the one
to use), `source` (`osm` | `gtfs`), `osm` (`{type, id, matched_by, distance_m}` or `null`), `gtfs` (`{lat, lon}`),
`members` (a rail platform's GTFS platform + track children), `group`, `parent`, `entrances` (metro: the station's
entrances `{gtfs_id, lat, lon, osm_id}`), `transfers` (metro: `{to, walk_m}` to the other platforms of the station),
`wheelchair`, `zone`; Veturilo also `capacity`, `virtual`.

```json
[{"id": "ztm:435102", "kind": "bus_post", "name": "Grójecka", "code": "02", "modes": ["bus"], "feed": "ztm",
  "position": {"lat": 52.199445, "lon": 20.9660556}, "source": "osm",
  "osm": {"type": "node", "id": 8242056144, "matched_by": "ref", "distance_m": 11.9},
  "gtfs": {"lat": 52.199339, "lon": 20.966028}, "members": [], "group": "ztm:4351", "parent": null,
  "entrances": [], "transfers": [], "wheelchair": "1", "zone": "1"}, "..."]
```

### `GET /api/stations/{station_id}`

One location. `404 {"detail": "unknown station id (use the mkuran id, e.g. ztm:700901)"}` for an unknown id.

### `GET /api/stations/report`

How the overlay was matched: `hash`, `built`, `seconds` (build time), `total`, `kinds` (locations per kind),
`matched` (OSM positions per kind), `entrances` (`{osm, gtfs}`), `mismatches` (posts whose OSM `ref` is more than
50 m away; kept at GTFS).

```json
{"hash": "6f5618a155bae5798380cd0495b80fa30fde2e22d40fc7d598cf8cee0613c0a4", "built": "2026-10-18T02:40:10",
 "kinds": {"bus_post": 6244, "tram_post": 610, "metro_platform": 39, "rail_station": 93, "rail_platform": 207, "veturilo": 349},
 "matched": {"bus_post": 5518, "tram_post": 598, "metro_platform": 31, "rail_platform": 160},
 "mismatches": [{"id": "ztm:104802", "osm_id": 2444668502, "distance_m": 127, "why": "ref too far"}, "..."],
 "entrances": {"osm": 260, "gtfs": 2}, "total": 7542, "seconds": 0.4}
```

### `GET /api/stations/health`

The street router's status (relayed): `modes`, `stations` (`{count, hash}`), `matrices` (`{status: ok | stale |
missing, stations_hash, matrices_stations_hash, built}`): whether the stop-to-stop matrices belong to the loaded
overlay and graphs. `503` when the router is not running.

## OSM street graph

Street graph from OpenStreetMap. The server builds the cache at start (about 17 s on the first run).
`mode` is `walk` (1.3 m/s), `bike` (4.2 m/s riding), `accessible` or `stroller` (1.3 m/s).
Cost = length / speed + expected wait at crossings (and 60 s per elevator).

### `GET /api/osm/graph/summary`

| Query | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | `walk` | `walk`, `bike`, `accessible` (wheelchair: walk without stairs, with elevators) or `stroller` (as accessible, plus steps with a stroller ramp) |

```json
{"vertices": 1792617, "edges_undirected": 2019691, "edges_directed": 4039382,
 "simplified_vertices": 623594, "simplified_edges_undirected": 850668,
 "signal_crossings": 7815, "other_crossings": 42063, "road_signals": 4178,
 "speed_m_s": 1.3,
 "waits_s": {"crossing_signals": 27.22222222222222, "crossing": 2.0, "traffic_signals": 0.0, "elevator": 60.0},
 "nodes_with_signal_timing_tags": 0}
```

Error: `400 {"detail": "mode must be walk, bike, accessible or stroller"}`.

### `GET /api/osm/nearest`

Nearest graph node to a point.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `lat`, `lon` | number | required | point (`lat` -90..90, `lon` -180..180, else `422`) |
| `mode` | string | `walk` | `walk`, `bike`, `accessible` or `stroller` |

```json
{"node": 8405597587, "lat": 52.2296575, "lon": 21.0122762, "distance_m": 7.02}
```

A `mode` other than `walk`, `bike`, `accessible` or `stroller` returns `400 {"detail": "mode must be walk, bike, accessible or stroller"}`.

### `GET /api/osm/route`

Street path between two points.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `from_lat`, `from_lon`, `to_lat`, `to_lon` | number | required | start and end (same ranges as above) |
| `mode` | string | `walk` | `walk`, `bike`, `accessible` or `stroller` |

Answered by the C++ street router (`algorithms/router/README.md`, `POST /route`). The start and the end join the
street graph through up to 6 nearest nodes (at most 30 m farther than the nearest one); these short access segments
are walked.

Answer: `seconds` (total time with the mode's default speeds), `walk_m` (metres walked, also a pushed bike),
`bike_m` (metres ridden), `wait_s` (expected waits that do not depend on speed: crossings and signals, where signal
nodes closer than 30 m by path form one junction paid once, and 60 s per elevator), `length_m` (= `walk_m` +
`bike_m`), `snap_m` (distance from start and end to the nearest usable graph node, in metres), `path` (list of
`[lon, lat]`, 5 decimals), `geometry` (the same as `[lat, lon]`), `legs` (one leg: `mode` `walk` / `bike`, `from` /
`to` as `{"id": null, "lonlat": [lon, lat]}`, `seconds`, `walk_m`, `bike_m`, `wait_s`, `path`, and `segments`: parts
of one kind covering the path, `{"kind", "path", "length_m"}`, kind `ride` / `push` (bike ridden / pushed) / `walk` /
`steps` / `elevator` / `metro_access`; ridden metres add up to `bike_m`, the rest to `walk_m`), `elevators` (`[lon, lat]` where the path boards
an elevator), `steps` (`[lon, lat]` where a flight of steps starts; in `accessible` / `stroller` only steps with a ramp the mode
may use, in `bike` none).

```json
{"seconds": 1268.5, "walk_m": 88.7, "bike_m": 3988.8, "wait_s": 250.6, "length_m": 4077.5, "snap_m": [4.0, 7.9],
 "path": [[21.0122, 52.2297], [21.01226, 52.22969], "..."], "geometry": [[52.2297, 21.0122], [52.22969, 21.01226], "..."],
 "elevators": [], "steps": [],
 "legs": [{"mode": "bike", "from": {"id": null, "lonlat": [21.0122, 52.2297]}, "to": {"id": null, "lonlat": [20.9652, 52.2196]},
           "seconds": 1268.5, "walk_m": 88.7, "bike_m": 3988.8, "wait_s": 250.6, "path": ["..."],
           "segments": [{"kind": "push", "length_m": 4.0, "path": [[21.0122, 52.2297], [21.01226, 52.22969]]},
                        {"kind": "ride", "length_m": 2867.1, "path": [[21.01226, 52.22969], "..."]},
                        {"kind": "push", "length_m": 10.1, "path": ["..."]},
                        {"kind": "ride", "length_m": 1121.7, "path": ["..."]},
                        {"kind": "push", "length_m": 74.6, "path": ["...", [20.9652, 52.2196]]}]}]}
```

Errors:
- `400 {"detail": "mode must be walk, bike, accessible or stroller"}` for a `mode` other than `walk`, `bike`, `accessible` or `stroller`.
- `422` when the start or the end is more than 1000 m from the street graph (e.g. outside Warsaw):
  `{"detail": "start is more than 1000 m from the street graph"}` (the first of `start`, `end` that is too far).
- `404` with a message when no path exists.
- `503` when the street router is not running (`{"detail": "street router not reachable at ..."}`), and while the
  server is still starting.

---

## Routing

`POST /api/routes` and `GET /api/geocode` are served by the same process as the data API
(`cd backend && uv run uvicorn main:app --reload`). CORS allows the origins in `CORS_ORIGINS`
(default the Vite dev server). JSON keys are camelCase and match `frontend/src/types.ts`.

Types:

| Type | Fields |
|---|---|
| `LatLng` | `[lat, lon]` (used in `path` and `Place.position`) |
| `LonLat` | `[lon, lat]` (GPS / GeoJSON order, used in a leg's `start` and `end`) |
| `Place` | `id`, `label`, `sublabel` (optional), `position` (`LatLng`), `isCurrentLocation` (optional bool) |
| `RouteLeg` | `mode` (`walk`, `bike` = own bike, `veturilo` = rented Veturilo bike, `bus`, `tram`, `metro`, `rail`), `from`, `to` (names), `fromId`, `toId` (StationLocations IDs or `null` for non-station places), `line` (or `null`), `durationMin`, `distanceM`, `start`, `end` (`LonLat`, mapped stop positions or the router's place endpoints), `path` (list of `LatLng`), `segments` (optional list; empty when unavailable), `stop` (optional, 1-based number of the intermediate stop the leg ends at), `approximatePath` (bool, optional, default `false`: `true` when GTFS has no shape for the trip and `path` only joins the stops in order; street legs never set it) |
| `RouteOption` | `id`, `title`, `legs`, `departure`, `arrival` (`HH:MM`), `durationMin`, `distanceM`, `walkDistance`, `bikeDistance`, `transfers`, `tags`, `waypoints` (optional, trips with stops) |

`segments` contains `{kind, path, lengthM}`: kind is `ride`, `push`, `walk`, `steps`, `elevator` or `metro_access`;
path is `[lat, lon]` and lengthM is metres. Segments preserve the router's consecutive parts within a leg.
Rented bikes keep mode `veturilo` even while pushed. Consumers must also accept legs without segments.

`walkDistance` includes walking and pushed-bike metres; `bikeDistance` includes ridden metres (own bike and Veturilo);
`distanceM` is the whole trip, including transit. Station IDs refer to `GET /api/stations`.
Street and transit legs meet at the same mapped station position even when the GTFS shape endpoint differs.
There are no `costPln` and `calories` any more: calories are worked out from the legs (`mode`, `distanceM`, `durationMin`; see `algorithms/calories.py`).

### `POST /api/routes`

Route options between two places, from the GTFS timetable, OSM walk/bike paths and live Veturilo
availability. Up to 6 options: a walk, a Veturilo ride, a Veturilo ride joined to one direct
public-transport ride (bike then bus/tram/metro/rail, or the ride then a bike), Veturilo between
two rides, direct rides, one transfer and two transfers. Boarding stops are chosen by OSM walk time
among the nearest posts, not by straight-line distance alone. A live bus or tram that is behind its
timetable, a GTFS-RT trip update, or a PKP PLK delay (when `PLK_KEY` is set) adds an
`opóźnienie N min` tag and shifts departure and arrival. Shape distances in the GTFS file are
kilometers and are stored as meters. Boarding stops are one post per stop group, so a big node does not fill the whole list.
Changes between platforms use `transfers.txt` and `pathways.txt` when a feed has them, and posts of the same stop group otherwise.
The clock is Europe/Warsaw. Before 04:00 the search uses the previous GTFS service day
(times at 24:00 and later).
`profile` `accessible` drops Veturilo and stops or trips marked wheelchair-inaccessible (`"2"`).
A line that appears in the current ZTM alerts gets the tag `Zmiana na trasie`.

Body (JSON): `from` (`Place`), `to` (`Place`), `profile` (`standard`, `slow`, `accessible` or `stroller`, default `standard`),
`when` (optional, Warsaw local `HH:MM` or an ISO datetime; empty means now),
`via` (optional list of `Place`, at most 5) and `order` (`given` or `optimal`).
Optional pace and filters: `walkKmh` (1–10), `bikeKmh` (0–45; 0 means no Veturilo), `stepFree` (bool),
`maxTransfers` (`0`, `1`, `2` or `null` = up to two), `excludedDistricts` (Warsaw district names),
`excludedPoints` (`position`, `radiusM`) and `body` (`wheelchair` `none` | `manual` | `electric`; a wheelchair
implies `accessible` routing and no Veturilo; `weightKg`, `heightCm`, `age` and `sex` are accepted but not used by the route search). A trip with stops plans the next leg from the
previous arrival plus 2 minutes at the stop. `order` `optimal` minimises a time estimate, not straight-line distance.

Optional `travel`: `transit` (default, the usual mixed options), `walk`, `accessible`, `stroller` or `bike`.
The other values return a street-only option without requiring GTFS or live feeds; `bike` means the user's own bike.
They also support `via`. Walk uses the accessible graph for an accessible profile, `stepFree` or a wheelchair,
and the stroller graph for the stroller profile. Explicit `accessible` / `stroller` travel selects that profile's
default walking speed (unless walkKmh overrides it). Bike legs use the bike graph. Accessible and stroller profiles
disable Veturilo. A zero cycling speed rejects an explicit own-bike request with 422.
Accessible options carry `bez schodów`; stroller options carry `schody tylko z rynnami` when the path takes steps
(with stroller rails), else `bez schodów`; routes with elevators carry `windy: N`.

Answer: list of `RouteOption`. Public-transport geometry follows the GTFS shape between the stops
boarded and alighted (by stop distances, else the shape with the stops projected on it). A trip without any shape
is still offered: its `path` joins every stop of the ride in order and the leg has `approximatePath: true`. Walk and bike geometry comes only from the street router, using StationLocations IDs
at stop and Veturilo endpoints (metro access includes the entrances). A missing street path drops the mixed
candidate. The result may be empty. No straight lines replace missing street paths.

Verified through a running local API and C++ router, with the repository's GTFS/OSM data:

```json
{"from": {"id": "centrum", "label": "Centrum", "position": [52.2297, 21.0122]},
 "to": {"id": "gdanski", "label": "Dworzec Gdański", "position": [52.2574, 20.9933]},
 "when": "2026-10-18T08:00", "profile": "accessible", "bikeKmh": 0, "maxTransfers": 0}
```

Abbreviated answer (paths shortened; optional segments omitted here):

```json
[{"id": "pt-ztm:M1:NdM:MLO", "title": "M1",
  "legs": [{"mode": "walk", "from": "Centrum", "to": "Centrum", "line": null,
            "fromId": null, "toId": "ztm:7013M:P1", "durationMin": 6, "distanceM": 327.1,
            "start": [21.0122, 52.2297], "end": [21.010385558, 52.231009364],
            "path": [[52.2297, 21.0122], "...", [52.23101, 21.01039]]},
           {"mode": "metro", "from": "Centrum", "to": "Dworzec Gdański", "line": "M1",
            "fromId": "ztm:7013M:P1", "toId": "ztm:7019M:P1", "durationMin": 6, "distanceM": 3190.8,
            "start": [21.010385558, 52.231009364], "end": [20.994182473076926, 52.25808857692308],
            "path": [[52.23106, 21.010189], "...", [52.257832, 20.994385]]},
           {"mode": "walk", "from": "Dworzec Gdański", "to": "Dworzec Gdański", "line": null,
            "fromId": "ztm:7019M:P1", "toId": null, "durationMin": 5, "distanceM": 227.2,
            "start": [20.994182473076926, 52.25808857692308], "end": [20.9933, 52.2574],
            "path": [[52.25809, 20.99418], "...", [52.2574, 20.9933]]}],
  "departure": "08:02", "arrival": "08:19", "durationMin": 17, "distanceM": 3745.1,
  "walkDistance": 554.3, "bikeDistance": 0, "transfers": 0, "tags": ["Najszybsza"]}]
```

The router rounds street paths to five decimals; stop endpoint metadata retains exact catalog positions.
The GTFS shape remains unchanged. In this example the access/egress segments also include `metro_access`.
For the same local dataset, Centrum [52.2297, 21.0122] → Ochota [52.2196, 20.9652] with
`travel: "bike"` returned 21 min, walkDistance 88.7 m (pushed) and bikeDistance 3988.8 m (ridden).

Errors: `422` when the body is not valid, when `when` is not `HH:MM` or an ISO datetime,
or an explicit street-only endpoint is outside the street graph. `404` when an explicit street-only request has no path.
Mixed planning skips street candidates rejected with 404/422. `503` when timetable/overlay data is missing
or the street router is unavailable. Other router errors retain their HTTP status.

### `GET /api/geocode`

Place search for the start and destination fields, limited to Warsaw. The answer lists our own places first: up to 4 stops
(one per stop name, at the centre of its posts, `sublabel` `Przystanek`, `id` `stop-<gtfs id>`) and Veturilo stations
(`sublabel` `Stacja Veturilo`, `id` `veturilo-<station id>`), matched on the start of any word without regard to case or Polish
accents (`marszalk` finds `Marszałkowska`). Then come OpenStreetMap Nominatim results (addresses and other places, up to 6, duplicates
and places already listed removed), only for texts of 3 or more characters.
Nominatim place IDs use `osm:<osm_type>:<osm_id>`; Nominatim results without an OSM object reference are omitted.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `q` | string, at least 1 character | required | search text |
| `lat`, `lon` | number | none | the user's position; equally good local matches are ordered by distance from it |

```json
[{"id": "osm:way:126234965", "label": "Koneser", "sublabel": "Praga-Północ",
  "position": [52.2555027, 21.0452825], "isCurrentLocation": null}, "..."]
```

Errors: `422` for an empty `q`, a `q` longer than 200 characters or a position out of range; `502 {"detail": "Geocoding service failed"}`
when Nominatim fails and no stop or station matched (when some matched, they are returned alone). The server keeps answers for 10 minutes, so a repeated search does not reach Nominatim.

### `GET /health`

Liveness check of the slim app `app.main:app` only: `{"status": "ok"}`. The main app (`main:app`) has no `/health`
(`404`); the street router's status is `GET /api/stations/health`.

---

## Speed history

Average walking / cycling / wheelchair speed from the user's own trips (`algorithms/speed_history.py`). Stateless:
the server stores and logs nothing. The device sends a GPS track once, gets records without coordinates back and keeps
only those.

### `POST /api/history/records`

Turns the GPS track of one ridden route into at most one record per mode. The moving distance is shared between the
legs by their planned distance; standing still, gaps over 60 s and GPS jumps (over 60 km/h) are not counted.
`walk` legs make a `walking` record (or `wheelchair` with `walkAs`), `bike` and `veturilo` legs a `cycling` record;
other legs only take their share. A mode needs at least 200 m and 60 s of movement and a plausible speed
(walking 1-10 km/h, cycling 3-45, wheelchair 1-15).

| Body field | Type | Meaning |
|---|---|---|
| `track` | list (at most 20000) of `{lat, lon, t}` | GPS points; `t` in seconds (any epoch, only differences matter) |
| `legs` | list (at most 30) of `{mode, distanceM}` | the legs of the route, in order (`mode` as in `RouteLeg`) |
| `walkAs` | `walking` (default) or `wheelchair` | what the walking legs count as |
| `at` | string, optional | ISO date-time of the trip; empty = now (UTC) |

Answer: `records`, each `{mode, distanceM, durationS, kmh, at}` (`mode` `walking`, `cycling` or `wheelchair`;
`durationS` = moving time). `[]` when the track is too short or does not match the route (0.5-2 times its distance).

```json
{"track": [{"lat": 52.2297, "lon": 21.0122, "t": 1792300000}, {"lat": 52.22975, "lon": 21.0122, "t": 1792300004}, "..."],
 "legs": [{"mode": "walk", "distanceM": 500}, {"mode": "veturilo", "distanceM": 2000}],
 "walkAs": "walking", "at": "2026-10-18T09:00:00+02:00"}
```

```json
{"records": [{"mode": "walking", "distanceM": 500.0, "durationS": 360.0, "kmh": 5.0, "at": "2026-10-18T09:00:00+02:00"},
             {"mode": "cycling", "distanceM": 2003.0, "durationS": 404.0, "kmh": 17.9, "at": "2026-10-18T09:00:00+02:00"}]}
```

Errors: `422` for a malformed body.

### `POST /api/history/summary`

Average speed per mode from the records the device keeps: the latest `window` records of each mode, average =
total distance / total moving time, records further than half the median from the median ignored (from 5 records).

| Body field | Type | Default | Meaning |
|---|---|---|---|
| `records` | list (at most 500) | required | records as `POST /api/history/records` returned them |
| `minTrips` | int 1-50 | `5` | `enough` is true from this many records |
| `window` | int 1-200 | `20` | latest records per mode that count |

Answer: `walking`, `cycling`, `wheelchair`, each `{trips, distanceKm, avgKmh, medianKmh, enough}` (`avgKmh` /
`medianKmh` are `null` without records). The app may use `avgKmh` as the speed setting when `enough` is true.

```json
{"walking": {"trips": 3, "distanceKm": 1.5, "avgKmh": 5.0, "medianKmh": 5.0, "enough": false},
 "cycling": {"trips": 3, "distanceKm": 6.0, "avgKmh": 17.8, "medianKmh": 17.9, "enough": false},
 "wheelchair": {"trips": 0, "distanceKm": 0.0, "avgKmh": null, "medianKmh": null, "enough": false}}
```

Errors: `422` for a malformed body or a value out of range (e.g. `minTrips: 0`).

---

## Journey statistics

### `POST /api/journeys`

Records one explicitly completed GPS recording, only when the user has opted in (off by default).
The frontend snapshots the selected whole-trip start and destination at recording start. Searches,
previews, mock routes, interrupted recordings and recordings without usable GPS are not submitted.
This is independent of the stateless speed-history endpoints.

Body: `token` (UUID, generated once per recording), `from` and `to` (each has `id`, `position`
as `[lat, lon]`, and optional `isCurrentLocation`, default false). No labels, full tracks,
user/device identifiers or personal preferences are accepted. Unknown fields are rejected.

- GTFS IDs (`ztm:...`, `wkd:...`, `pkp:...`) and Veturilo IDs (`vet:...`) resolve to catalog coordinates.
- OSM object references (`osm:node:...`, `osm:way:...`, `osm:relation:...`) retain the selected object's coordinates.
- `id: "current-location"` with `isCurrentLocation: true` resolves to the nearest boarding stop/platform
  or Veturilo station, by geographic distance (ties by ID). Only that anchor's ID and exact coordinates
  are persisted; the supplied GPS point is not stored. There is no distance cutoff or spatial grid.

SQLite stores places and daily Warsaw-time origin-destination counts in `db/journey_stats.sqlite`
(override with `JOURNEY_STATS_DB`). A token-only receipt makes retries atomic and idempotent:
the first submission returns `200 {"recorded": true}`, and repeats return `200 {"recorded": false}`.
There are no individual journey timestamps or links between different recordings or users.
Counters and receipts are retained until the operator clears the database. There is no public read/export API.
Counts represent completed recordings with selected endpoints, not verified arrival at the destination.

The database and anchor catalog are initialized at server startup from local GTFS and GBFS files.
Requests never download data or build caches. Statistics failures do not block the frontend's local
speed-history saving; it makes at most one retry with the same token while sharing remains enabled.

Errors: `422` for malformed input or unknown catalog IDs; `503 {"detail": "journey statistics unavailable"}`
when initialization/data is unavailable or a database write fails. New statistics logs contain no
coordinates, labels, request bodies, tokens or user identifiers.

Verified against a running local server (isolated temporary database):

```json
{"token": "c1b57903-37b5-418d-8e75-cde286eb5a11",
 "from": {"id": "current-location", "position": [52.248455, 21.044827], "isCurrentLocation": true},
 "to": {"id": "vet:203610", "position": [52.25602, 21.046219]}}
```

First answer: `{"recorded": true}`. Repeating that exact request: `{"recorded": false}`.

## Simulation (only with `SIM_SCENARIO`)

For integration tests and demos. Start the server with `SIM_SCENARIO=<name>` (a file
`integration/scenarios/<name>.json`, see `integration/README.md`). Then:

- the live feeds replay the scenario on a simulated clock: `GET /api/live/vehicles` (recorded or made from
  GTFS), Veturilo status (saved GBFS file + changes from the scenario) and ZTM alerts. No external API is called,
  and `PORTAL_KEY` is not needed;
- `/api/live/nearest-buses`, `/api/live/delay` and departures use the simulated time. The route engine reads the
  real clock: send the simulated `time` from `GET /api/sim/state` as `when` in `POST /api/routes`;
- the 3 s vehicle poller is off: each `POST /api/sim/clock` reads the feed once.

Without `SIM_SCENARIO` these endpoints do not exist (`404`).
`t` and `start` are epoch seconds; `time` is Warsaw local time.

### `GET /api/sim/state`

Clock time and the loaded scenario.

```json
{"scenario": "trip-gorczewska-daszynskiego", "source": "gtfs", "start": 1792564200.0,
 "title": "Osiedle Gorczewska -> Rondo Daszynskiego by bus and tram", "t": 1792564200.0,
 "time": "2026-10-21T08:30:00", "elapsed_s": 0.0}
```

### `POST /api/sim/clock`

Set and / or move the clock, then bus detection reads the feed at the new time. Answer: same as `GET /api/sim/state`.

| Body field | Type | Meaning |
|---|---|---|
| `t` | number, optional | set the clock to this epoch (s) |
| `step_s` | number 0-3600, optional | then move it forward by this many seconds |

```json
{"step_s": 60}
```

```json
{"scenario": "trip-gorczewska-daszynskiego", "source": "gtfs", "start": 1792564200.0,
 "title": "Osiedle Gorczewska -> Rondo Daszynskiego by bus and tram", "t": 1792564260.0,
 "time": "2026-10-21T08:31:00", "elapsed_s": 60.0}
```

### `GET /api/sim/scenario`

The loaded scenario file as JSON (`title`, `source`, `start`, `trip`, `test`, and optional `recording`,
`delays`, `alerts`, `veturilo`).

```json
{"title": "Osiedle Gorczewska -> Rondo Daszynskiego by bus and tram", "source": "gtfs", "start": "2026-10-21T08:30:00",
 "trip": {"from": {"id": "os-gorczewska", "label": "Osiedle Górczewska", "position": [52.2397, 20.907]}, "...": "..."}}
```

### `POST /api/sim/scenario`

Load another scenario, forget all vehicles of the previous one and set the clock to its start.
Body: `{"name": "recorded-bus-ride"}` (lowercase letters, digits and `-`, else `422`).
Answer: same as `GET /api/sim/state`.

```json
{"scenario": "recorded-bus-ride", "source": "recorded", "start": 1792243404.1179507,
 "title": "Which bus am I on? (2-minute recording)", "t": 1792243404.1179507,
 "time": "2026-10-17T15:23:24", "elapsed_s": 0.0}
```

Error: `404 {"detail": "unknown scenario"}`.

### `GET /api/sim/scenarios`

Every scenario file in `integration/scenarios/` (the demo lists them). `trip` is `null` for a scenario
without a planned trip.

```json
[{"name": "trip-gorczewska-daszynskiego", "title": "Osiedle Gorczewska -> Rondo Daszynskiego by bus and tram",
  "source": "gtfs",
  "trip": {"from": {"id": "os-gorczewska", "label": "Osiedle Górczewska", "position": [52.2397, 20.907]},
           "to": {"id": "rondo-daszynskiego", "label": "Rondo Daszyńskiego", "position": [52.2303, 20.984]},
           "profile": "standard"}}, "..."]
```

### `POST /api/sim/ride`

Simulate a user who travels a route option and return the whole timeline (the demo plays it back). The user leaves at
`option.departure`, walks, waits for a synthetic vehicle of the planned line, rides it and walks on. Takes 30-60 s for a
long trip, one ride at a time (`409` if no scenario is loaded). Afterwards the clock and the vehicles go back to the
scenario start, so the next ride starts from the same state.

| Body field | Type | Meaning |
|---|---|---|
| `option` | object | a `RouteOption` as `POST /api/routes` returns it |
| `profile` | string, default `standard` | walking / cycling pace profile (`standard`, `slow`, `accessible`) |
| `noiseM` | number 0-100, default 15 | GPS error, standard deviation per axis (m) |
| `seed` | integer, default 1 | the same seed gives the same ride |

Answer: `ok` / `reason` (the ride failed, e.g. no vehicle came in 30 min), `start` / `end` (epoch s), `plan` (legs with
`mode`, `line`, `path`), `fixes` (every 5 s: `lat` / `lon` what the phone reports, `trueLat` / `trueLon` where the user is,
`leg` index, `vehicle` id while riding), `events` (`board` / `alight`), `detections` (every 10 s while riding: the
candidates `POST /api/live/nearest-buses` returned for the last 3 fixes).

```json
{"ok": true, "reason": "", "start": 1792564260.0, "end": 1792566410.0,
 "plan": [{"mode": "walk", "line": null, "path": [[52.2397, 20.907], "..."]}, "..."],
 "fixes": [{"t": 1792564265.0, "lat": 52.239712, "lon": 20.907031, "trueLat": 52.239701, "trueLon": 20.907018,
            "leg": 0, "vehicle": null}, "..."],
 "events": [{"t": 1792565100.0, "event": "board", "line": "11", "vehicle": "tram-S11-3", "waitedS": 120.0}, "..."],
 "detections": [{"t": 1792565130.0, "vehicle": "tram-S11-3",
                 "candidates": [{"id": "tram-S11-3", "mode": "tram", "line": "11", "direction": "Sielce",
                                 "vehicle": "S11-3", "brigade": "3", "rmse_m": 20.1}, "..."]}, "..."]}
```

Errors: `422 {"detail": "bad option: ..."}` (a broken option), `409 {"detail": "no scenario loaded"}`.

In simulation mode `GET /api/live/vehicles` keeps its form. A vehicle made from GTFS has
`vehicle` = `S<line>-<brigade>` (e.g. `S521-3`); a recorded one keeps its real number:

```json
[{"line": "161", "brigade": "2", "lat": 52.162864, "lon": 21.212823, "time": "2026-10-17 15:23:04",
  "vehicle": "1000", "mode": "bus", "route_id": "ztm:161"}, "..."]
```

