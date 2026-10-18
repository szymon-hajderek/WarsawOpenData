# Preserve actual route paths

- Repair GTFS cache validation so a legacy feed with truncated kilometre distances rebuilds even if
  another feed has large values. Use format version 2 to include the current platform/boarding fields
  and migrate the local version-1 caches left by closed PR #82 as well.
- Preserve actual road/track geometry in the map overlay instead of adding straight connectors from
  route endpoints to offset stop markers. Keep stop markers, metro entrance overlays and underground styling.
- Keep GTFS vertices in `shape_pt_sequence` order. Recover shapes for feeds with missing/unusable
  distance measures (notably WKD) by projecting ordered stops onto the actual polyline, preserving bends.
- Expose the graph portion of street paths as `network_geometry` / `RouteLeg.networkPath` for map drawing.
  Full paths, access costs, selected place/GPS coordinates and distance/time calculations remain intact.
  No C++ change/rebuild is needed.
- Keep route engine selection, modes, transfers, mixed Veturilo options, multi-stop behavior and existing
  missing-data fallback availability unchanged. Prefer recovered real geometry before the existing fallback.
  Do not relocate addresses or GPS points or fetch building entrances.
- Add regression tests for cache migration, distance precision and new platform fields, curved transit
  paths, route availability with missing geometry and unchanged overlay paths across all transport modes.
- Environment: backend restart rebuilds old GTFS caches from existing ZIPs; no dependency, external
  service, key or download is added. Update the API contract for the two additive geometry fields and
  shape recovery behavior; existing endpoints, fields and errors keep their meaning.
- Scope limit: access costs and full paths retain the existing coordinate-to-graph connectors. The map
  draws the graph portion; this is not building obstacle routing. Genuine missing-data fallbacks remain
  available, rather than deleting their route options.
- Validation: 237 backend/algorithm tests passed, 6 C++ tests skipped and 2 C++ server cases deselected
  on Windows (the full native run cannot launch the Linux executable). Frontend: 83 tests, lint and
  production build passed. Live temporary API checks used the running WSL C++ router.
- Real-data audit: 2,534 unique eligible GTFS shapes use source geometry, including all 1,576 ZTM bus,
  322 tram and 4 metro variants, 37 WKD variants recovered by stop projection and 585 PKP rail variants.
  One PKP replacement-bus entry has no shape in the source and retains its existing fallback.
- Original-coordinate MIM UW to Palace of Culture: 268 street graph points walking, 304 cycling,
  280 accessible walking. Full paths and costs are unchanged; the planner retains walking and Veturilo options.
