# feature/route-format-v2

New route format from the user (see `data/API.md`):

- `RouteOption`: `walkDistance` and `bikeDistance` added (sums of the `walk` legs and of the `bike` + `veturilo` legs, filled by the model from the legs); `costPln` and `calories` removed.
- `RouteLeg.mode`: `veturilo` (rented, what `bike` was) and `bike` (own bike, nothing produces it yet). A leg has `start` / `end` as `[lon, lat]`, filled from its `path`; `path` stays `[lat, lng]`.
- Backend: `models.py`, `real_engine.py` (no fares, no calories, no body plumbing; `body.wheelchair` still means accessible routing), `stub_engine.py`, `multi.py`. Only the "Najszybsza" tag remains.
- Calories are worked out from the legs: `algorithms/calories.py` takes `bike` and `veturilo`, and uses the leg's own speed (distance / time) when the leg has a time. The frontend `routeKcal` does the same.
- Frontend: types, mock routes, `modes.tsx` (Veturilo + own bike), list and details no longer show a price, "Najtańsze" sort and the "Najtańsza" / "Najaktywniejsza" tags removed, filter chip "Veturilo".
- Speed history: `veturilo` and `bike` legs both count as cycling. Integration tests use the `veturilo` mode.
- Assumptions: `walkDistance` / `bikeDistance` in metres like `distanceM`; the request field `body` is kept (weight, height, age and sex are accepted but unused); `algorithms/fares.py` and the fare readers in `sources/mkuran.py` stay in the repo, unused by the route engine (delete them if the price is gone for good).
- Not checked: the real engine against real data (needs the GTFS / OSM files; Git LFS pointers on this machine), integration tests (`integration/`, need those files). Backend tests (`backend/tests`, `algorithms`) and the frontend tests pass; one test (`test_upstream_failure_gives_502_without_the_key`) fails on `main` as well.
