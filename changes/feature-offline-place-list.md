# feature/offline-place-list

- The place search works without the backend: `frontend/src/data/places.json` (2985 stop names and 349 Veturilo stations, `[name, lat, lon, kind]`, 132 KB, 45 KB gzipped) is searched in the browser from 2 characters on; Nominatim adds addresses from 3 characters. With the backend, nothing changes.
- `backend/export_places.py` writes the file from the GTFS and Veturilo data (one entry per stop name, at the centre of its posts). It was run on today's data in a scratch copy; run it again when the timetable or the stations change.
- `frontend/src/utils/placeSearch.ts`: the TypeScript twin of `algorithms/place_search.py` (same rules), with tests.
- `searchPlaces`: the bundled list answers when the backend is down; if Nominatim fails too, the stops found are still returned. `MIN_QUERY` is 2 in both modes.
- Assumptions: the file is committed (not generated at build time, so a frontend-only checkout works); ids of these places look like `stop-local-<n>` and are only used inside the UI (routes use the position).
