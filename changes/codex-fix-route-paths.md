# GTFS geometry data repair

- Version the GTFS cache so truncated kilometre distances cannot hide behind another feed's large values.
  Rebuild older caches from existing ZIPs; retain the current platform/boarding schema.
- Keep shape vertices in `shape_pt_sequence` order and reject missing or non-monotonic distance measures.
- Add `shape_by_stops` and a pure projection helper to recover the actual source shape for feeds such
  as WKD that omit stop-to-shape distances, preserving bends and ordered loops.
- Add data regression tests and update the concurrent cache test's version marker.
- No changes to the route engine, API contract, router-owned files or frontend. Engine integration belongs
  to PR #85, after this data change merges. Station endpoints and full access paths keep their existing meaning.
- Setup: restart the backend to rebuild old caches automatically; no new dependency, key or download.
