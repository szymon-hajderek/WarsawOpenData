# fix/place-search

- Matching (`algorithms/place_search.py` and its twin `frontend/src/utils/placeSearch.ts`): words of letters and digits,
  every query word at a word start in any order, numbers whole, Polish abbreviations both ways (ds, pl, al, dw, os, uw, pw),
  `nr` / `ul` ignored, aliases; quality 0-4 with well-known places first on ties. Match data is computed once per index.
- Well-known places: `data/places/landmarks.json` (43 entries: universities, UW dormitories, malls, stations, airports,
  landmarks) in the backend index and in `frontend/src/data/places.json` (kind 2 rows).
- `GET /api/geocode?source=local|nominatim|all`: local answers in ~8 ms; Nominatim with a 1.5 s timeout, 1 h cache,
  1 s spacing (skip when the wait would be > 1 s), 30 s pause after a 429, one keep-alive client. Addresses put
  Nominatim first. The local index is built in the server warm-up.
- Frontend: `searchPlaces` shows local places at once (`onLocal`), asks Nominatim 350 ms later and merges; `PlaceField`
  debounce 300 -> 150 ms and passes `onLocal`.
- Tests: the user's query list in `algorithms/test_place_search.py` and `placeSearch.test.ts`; Nominatim cache / rate gate /
  429 in `backend/tests/test_geocode_sources.py`; streaming and merging in `src/api/geocode.test.ts`.
