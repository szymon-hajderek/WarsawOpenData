# API

This file is the **contract** of the backend API (FastAPI, `backend/`). Frontend and backend code must match it.
To change the API, edit this file first, then the code, in the same PR (see `AGENTS.md`).

- Base URL in development: `http://localhost:8000`. Two apps: the data API (`cd backend && uv run uvicorn main:app --reload`)
  and the routing API (`cd backend && uvicorn app.main:app --reload`, section at the end). Run one at a time.
- Interactive docs generated from the code: `/docs`, schema: `/openapi.json`.
- All answers are JSON. Errors have the form `{"detail": "<message>"}`.
- Errors that any endpoint can return (they are not repeated below):
  - `422` for a query value that is out of range or in the wrong form (e.g. `limit=-1`, `lat=999`, `bbox=1,2`).
  - `502 {"detail": "external data source failed, try again later"}` when an external API (City Hall, Nextbike)
    fails. The message never contains the URL or a key.
  - `503` when a key in the server `.env` is empty (the message names it), or, for `/api/gtfs`, `/api/osm`,
    `/api/routes` and `/api/live/nearest-buses`, while the server loads its caches at start (about 1-2 minutes
    after a start, longer on the first run). The header `Retry-After: 30` is set.
  - `404` when a data file is missing on the server (run `download.py`, or `report.py` for `/api/stats`).
- Users never call external APIs. Only the server does, and it caches the answers.
- No authentication on our side. The keys for City Hall endpoints live in `.env` on the server (`ACCESS.md`).
- Examples below are real answers from a running server. Long lists are cut to 1-2 items and end with `"..."`.
- Coordinates are WGS84 `lat` / `lon` in degrees. Times are Warsaw local time.
- Endpoints: 26 (data API 23: meta 2, GTFS 8, live and City Hall 4, bus detection 1, Veturilo 5, OSM 3;
  routing API 3).

| Group | Prefix | Source file |
|---|---|---|
| [Meta](#meta) | `/api` | `backend/main.py` |
| [GTFS](#gtfs-timetables-and-stops) | `/api/gtfs` | `backend/sources/mkuran.py` |
| [Live vehicles](#live-vehicles-and-city-hall) | `/api/live`, `/api/ztm` | `backend/sources/um_warszawa.py` |
| [Bus detection](#bus-detection) | `/api/live` | `backend/bus_detect.py` |
| [Veturilo](#veturilo-city-bikes) | `/api/veturilo` | `backend/sources/nextbike.py` |
| [OSM](#osm-street-graph) | `/api/osm` | `backend/sources/osm.py` |
| [Routing API](#routing-api-backendapp) | `/api/routes`, `/api/geocode`, `/health` | `backend/app/` |

## IDs

- Stop ids carry a feed prefix: `ztm:700901`, `wkd:brzoz`, `pkp:33605_RAIL_1_5`.
  ZTM `700901` = group `7009` + post `01`.
- Route ids: `ztm:131`. Group ids: `ztm:7009`. Veturilo station: `station_id` (`203610`), global id `vet:203610`.
- `line` in live endpoints = GTFS `route_short_name`; `route_id` = `ztm:<line>`.
- Veturilo and OSM have no shared ids with GTFS: join them by distance.

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
`item3_osm`, `item4_feasibility`, `compatibility`, `seconds_to_build`, `endpoints`.

```json
{
 "generated": "2026-10-17T14:48:45",
 "reference_date": "20261021",
 "vertices": {"transit_posts": 7145, "transit_stop_groups": 3046, "veturilo_stations": 349,
              "osm_walk": 1534865, "osm_bike": 1000177, "...": "..."},
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
`same_as` (id of the station this stop is merged into, or `null`).

```json
[
 {"id": "ztm:100101", "feed": "ztm", "raw_id": "100101", "name": "Kijowska", "code": "01",
  "lat": 52.248455, "lon": 21.044827, "location_type": 0, "parent": null, "wheelchair": "1",
  "zone": "1", "group": "ztm:1001", "modes": ["bus"], "served": true, "same_as": null},
 "..."
]
```

### `GET /api/gtfs/stops/{stop_id}`

One stop. Same fields as above. `404` for an unknown id.

```json
{"id": "ztm:700901", "feed": "ztm", "raw_id": "700901", "name": "Marszałkowska", "code": "01",
 "lat": 52.217931, "lon": 21.020112, "location_type": 0, "parent": null, "wheelchair": "2",
 "zone": "1", "group": "ztm:7009", "modes": ["bus"], "served": true, "same_as": null}
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

---

## OSM street graph

Walk and bike graph from OpenStreetMap. The first call builds a cache (about 45 s).
`mode` is `walk` (1.3 m/s) or `bike` (4.2 m/s). Cost = length / speed + expected wait at crossings.

### `GET /api/osm/graph/summary`

| Query | Type | Default | Meaning |
|---|---|---|---|
| `mode` | string | `walk` | `walk` or `bike` |

```json
{"vertices": 1534865, "edges_undirected": 1741689, "edges_directed": 3483378,
 "simplified_vertices": 548631, "simplified_edges_undirected": 755455,
 "signal_crossings": 7708, "other_crossings": 38148, "road_signals": 4047,
 "speed_m_s": 1.3,
 "waits_s": {"crossing_signals": 27.22, "crossing": 2.0, "traffic_signals": 0.0},
 "nodes_with_signal_timing_tags": 0}
```

Error: `400 {"detail": "mode must be walk or bike"}`.

### `GET /api/osm/nearest`

Nearest graph node to a point.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `lat`, `lon` | number | required | point (`lat` -90..90, `lon` -180..180, else `422`) |
| `mode` | string | `walk` | `walk` or `bike` |

```json
{"node": 8405597587, "lat": 52.2296575, "lon": 21.0122762, "distance_m": 7.02}
```

A `mode` other than `walk` or `bike` returns `400 {"detail": "mode must be walk or bike"}`.

### `GET /api/osm/route`

Street path between two points.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `from_lat`, `from_lon`, `to_lat`, `to_lon` | number | required | start and end (same ranges as above) |
| `mode` | string | `walk` | `walk` or `bike` |

Answer: `mode`, `seconds` (total time with waits), `length_m`, `wait_s` (expected wait at crossings),
`nodes` (count), `snap_m` (distance from start and end to the graph, in metres), `geometry` (list of `[lat, lon]`).

```json
{"mode": "bike", "seconds": 765.7, "length_m": 2452.6, "wait_s": 181.7, "nodes": 154,
 "snap_m": [4.0, 4.2], "geometry": [[52.2296943, 21.0122579], [52.229818, 21.0122376], "..."]}
```

Errors:
- `400 {"detail": "mode must be walk or bike"}` for a `mode` other than `walk` or `bike`.
- `422` when the start or the end is more than 1000 m from the street graph (e.g. outside Warsaw):
  `{"detail": "start is 224509 m from the street graph (max 1000 m)"}` (`start`, `end`, or both).
- `404` with a message when no path exists.

---

## Routing

`POST /api/routes` and `GET /api/geocode` are served by the same process as the data API
(`cd backend && uv run uvicorn main:app --reload`). CORS allows the origins in `CORS_ORIGINS`
(default the Vite dev server). JSON keys are camelCase and match `frontend/src/types.ts`.

Types:

| Type | Fields |
|---|---|
| `LatLng` | `[lat, lon]` |
| `Place` | `id`, `label`, `sublabel` (optional), `position` (`LatLng`), `isCurrentLocation` (optional bool) |
| `RouteLeg` | `mode` (`walk`, `bike`, `bus`, `tram`, `metro`, `rail`), `from`, `to` (names), `line` (or `null`), `durationMin`, `distanceM`, `path` (list of `LatLng`) |
| `RouteOption` | `id`, `title`, `legs`, `departure`, `arrival` (`HH:MM`), `durationMin`, `distanceM`, `calories`, `transfers`, `costPln`, `tags` |

### `POST /api/routes`

Route options between two places, from the GTFS timetable, OSM walk/bike paths and live Veturilo
availability. Up to 6 options: a walk, a Veturilo ride, direct rides and one transfer.
`profile` `accessible` drops Veturilo and stops or trips marked wheelchair-inaccessible (`"2"`).
A line that appears in the current ZTM alerts gets the tag `Zmiana na trasie`.

Body (JSON): `from` (`Place`), `to` (`Place`), `profile` (`standard`, `slow` or `accessible`, default `standard`).

Answer: list of `RouteOption`. Public-transport geometry follows the GTFS shape between the stops
boarded and alighted. Walk and bike geometry follows the OSM graph (a straight line only when the
graph has no path).

```json
[{"id": "pt-ztm:trip", "title": "175",
  "legs": [{"mode": "walk", "from": "Start", "to": "Marszałkowska", "line": null,
            "durationMin": 4, "distanceM": 280,
            "path": [[52.2297, 21.0122], [52.231, 21.015], "..."]},
           {"mode": "bus", "from": "Marszałkowska", "to": "Metro Politechnika", "line": "175",
            "durationMin": 12, "distanceM": 2400, "path": [[52.231, 21.015], "..."]}],
  "departure": "15:59", "arrival": "16:18", "durationMin": 19, "distanceM": 2800,
  "calories": 15, "transfers": 0, "costPln": 3.4, "tags": ["Najszybsza"]}, "..."]
```

Errors: `422` when the body is not valid. `503` when the GTFS zip is not on disk.

### `GET /api/geocode`

Place search: proxy to OpenStreetMap Nominatim, limited to Warsaw, up to 6 results, duplicates removed.

| Query | Type | Default | Meaning |
|---|---|---|---|
| `q` | string, at least 1 character | required | search text |

```json
[{"id": "osm-177963717", "label": "Dworzec Centralny", "sublabel": "Aleje Jerozolimskie 54, Śródmieście",
  "position": [52.2288747, 21.0040358], "isCurrentLocation": null}, "..."]
```

Errors: `422` for an empty `q` or a `q` longer than 200 characters; `502 {"detail": "Geocoding service failed"}`
when Nominatim fails. The server keeps answers for 10 minutes, so a repeated search does not reach Nominatim.

### `GET /health`

Liveness check: `{"status": "ok"}`.
