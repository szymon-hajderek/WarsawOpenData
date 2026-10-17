# feature/python-route-search

- Second transfer, with tight caps. `transfers.txt` and `pathways.txt` feed the change graph; posts in one stop group are a 60 s station walk. Warsaw has no pathways file, so that reader is empty.
- Boarding stops are re-ranked by OSM walk time (up to 12 candidates). The straight-line scan only builds the candidate pool.
- GTFS-RT trip updates (WKD and polish_trains) and, when `PLK_KEY` is set, PKP PLK delays shift the clock. A failed feed does not fail the route. Bus and tram lateness from positions is unchanged.
- WKD price comes from `fare_attributes.txt`. SKM uses the ZTM ticket. KM has no fare file, so a KM ride stays 7 zł.
- A multi-stop trip plans the next segment from the previous arrival plus 2 minutes. "Optimal" order minimises a time estimate (walk under 700 m, otherwise a wait plus transit), not straight-line metres.
- `POST /api/routes` accepts `walkKmh`, `bikeKmh` (0 = no Veturilo), `stepFree`, `maxTransfers` (0–2, empty = 2), `excludedDistricts`, `excludedPoints` and `body`. Calories use the same net-kcal formula as the app. The UI sends these fields.
- `bus_detect` reads feed times as `Europe/Warsaw` (`tzdata` on Windows).
- `update_state` is still a no-op until the C++ engine exists.
