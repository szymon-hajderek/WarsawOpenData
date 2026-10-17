# Anonymized journey logs (issue #52)

- Collect only the whole-trip start and destination of explicitly finished GPS recordings, with a separate opt-in disabled by default.
- Retain concrete object IDs and coordinates; resolve current-location endpoints to the nearest transit stop or Veturilo station.
- Store daily origin-destination counters in SQLite without full tracks or user/device identifiers; deduplicate retries by recording token.
- Keep statistics failures independent of speed history. No per-leg logging, public statistics API or spatial grid.
- Use OSM object references for place identities and remove operational logs of selected place labels.
- Validate nearest-anchor selection, atomic concurrent retries, persistence across restarts, input privacy,
  endpoint snapshots, mock/interrupted recordings and consent revocation (including another browser tab).
- Verify API examples against a running local server with an isolated temporary SQLite database.
