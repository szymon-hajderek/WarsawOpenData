# fix/backend-review

Fixes from a review of `backend/` (locks, atomic cache files, bounded cache, input checks, error codes).

- `osm.py`, `mkuran.py`: lazy cache builds sit behind a lock; no half-filled graph is visible to other threads.
- Cache files are written atomically (`config.atomic_write`, `save_json`, `save_npz`); the GTFS `.npz` is written
  last, so a crash never leaves a cache that looks complete. Downloads write `*.part` and rename.
- `TTLCache`: thread-safe, at most 256 entries, expired entries are dropped. `/api/ztm/...` checks `stop_id` and
  `line` before the cache.
- The server builds the GTFS and OSM caches at start in a background thread. Endpoints that need them answer
  503 (`Retry-After: 30`) until then. Users never start a build.
- Query checks (422): `bbox`, `date`, `time`, `limit`, `offset`, `lat`/`lon` ranges, `max_age_s`.
- Error codes: external API failure -> 502 (no URL or key in the text), empty key -> 503, missing data file -> 404.
- `bus_detect`: forgets vehicles silent for 5 min; waits 2 s before the first poll; fixed 503 text. It still reads
  our own server over HTTP.
- Geocode: 10 min cache (Nominatim limit), `q` up to 200 chars, bad JSON -> 502.
- `osm.api_route` snaps each point once (`route_nodes`); `osm.counts` and `report.py` use vectorised code.
- `report.py` no longer changes the cached `edges()` result.
- Tests: `backend/tests/test_robustness.py`.
- Docs: `data/API.md` (error codes and ranges), `README.md`, `AGENTS.md`.

Assumptions: LOW items of the review and the offline `app.main` app are untouched; `requirements.txt` only got a comment.
