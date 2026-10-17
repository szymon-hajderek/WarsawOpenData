# feature/place-search

- Place search now finds our own stops and Veturilo stations first. `GET /api/geocode` matches the start of any word without case and Polish accents (`marszalk` -> `Marszałkowska`), from 2 characters, and adds Nominatim results (3+ characters) after them.
- If Nominatim is down, the stops and stations that matched are still returned (it was always a 502 before).
- New optional `lat` / `lon` (the user's position): equally good local matches are ordered by distance.
- `algorithms/place_search.py` (+ tests): `fold`, `match_score`, `search`, `group_by_name` (posts of one stop become one place).
- Frontend: `searchPlaces(query, signal, near)`, `MIN_QUERY` (2 with the backend, 3 without), debounce 450 -> 300 ms, the field passes the user's position.
- Checked on real GTFS + Veturilo data in a scratch copy (queries `marszalk`, `politechn`, `centr`, `ur`, `wilanow`).
- Assumptions: no new external service (Photon etc.); up to 4 local results; the local index is built on the first search and kept in memory; a Nominatim result with the same name as a stop already listed is dropped.
- Not done: street-number / address autocomplete from OSM data (Nominatim still decides there), showing the transport mode of a stop.
