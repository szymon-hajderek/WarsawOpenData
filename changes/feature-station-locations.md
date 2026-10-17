# feature/station-locations

Builds on `feature/cpp-router` (PR #62). Building blocks for RAPTOR, not RAPTOR itself.

- Global GTFS -> OSM mapping (data layer, `backend/stations.py`, pure rules in `algorithms/station_map.py`): exact
  `ref` matches for posts, platform-number matches for rail platforms, nearest `subway_entrance` for metro entrances;
  GTFS is the authority and the fallback; Veturilo is not mapped.
- StationLocations overlay `data/derived/stations.json`: one record per transport node (bus / tram post, metro
  platform, rail platform or station, Veturilo) with mkuran ids, OSM position when matched, entrances and in-station
  transfers for metro, an integrity hash. Served by `GET /api/stations` and loaded by the C++ router.
- Rail: a location is a platform (`pkp:<station>_P<n>`, members = GTFS platform + track children); SKM comes from
  `polish_trains.zip` (platforms) instead of `warsaw.zip`.
- Router: `from` / `to` accept station ids; `POST /access` = one multi-source Dijkstra from a point (or to it) to
  every station within a time limit; `/health` reports the overlay hash and whether the matrices are stale.
- Matrices are computed on the overlay positions and carry the hash; a mismatch at start is reported, not recomputed.
- Street model: steps with `ramp:wheelchair=yes` are step-free in `accessible`. New mode `stroller` (graph, matrix,
  router): also takes steps with `ramp:stroller=yes`; a bike is pushed along the stroller graph.
