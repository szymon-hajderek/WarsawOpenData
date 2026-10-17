# Restore actual route geometry for every mode

- Rebuild unversioned or incompatible GTFS caches instead of inferring distance units from a maximum across feeds.
- Stamp the final atomic NPZ with a cache version and keep that metadata out of stop-time arrays.
- Replace truncated kilometre values with metre distances rebuilt from raw GTFS, allowing actual bus, tram, metro and rail shapes to be used.
- Add regression coverage for mixed-feed legacy data, cache reuse, incompatible versions, missing fields, precision and concurrent builds.
- Omit options with missing C++ street paths or GTFS shapes instead of drawing straight-line substitutes
  between endpoints or stops. Preserve the actual OSM street path and GTFS shape for successful searches.
- Use mapped public OSM building entrances for geocoded starts and destinations in every route mode,
  instead of building representative points. Handle ways and multipolygon relations; prefer main entrances
  and exclude private, forbidden, service and courtyard entrances. Cache object lookups for one day.
- Missing entrances or OSM lookup failures retain the original search point. Arbitrary GPS points and
  buildings without mapped entrances still depend on existing street graph access connections; this does
  not add building obstacles to the C++ router or guarantee obstacle-free access in those cases.
- Document the automatic cache rebuild and reselecting start/destination search results after a backend
  restart. No new dependencies, keys, manual data downloads or API fields. Entrance lookups use outbound
  HTTPS to the public OSM API; the API contract documents missing-geometry behavior.
- Regression tests cover cache migrations and fractional distances for all four transit types, entrance
  selection/caching/errors and missing street/transit geometry.
- Real-data validation: all 1,576 bus, 322 tram, 4 metro and 35 rail shapes in Warsaw ZTM produce the exact
  GTFS shape through the route engine after migration (zero missing full-trip geometries). All 16 M1/M2
  templates also pass the earlier check. Shapes come from the operator feed, not shortest street guesses.
- Live API MIM UW to Palace of Culture: mapped entrances, walk 293 points, bike 327 points and accessible
  walk 298 points. Walk/bike paths have no intersections longer than 0.5 m with either building footprint.
  The planner returns a 47-minute walk and a 31-minute Veturilo option with actual street geometry.
- Final automated validation: 235 backend/algorithm tests passed; 4 native C++ executable tests were
  skipped on Windows. The running WSL C++ router was exercised by the live API walk/bike/accessible checks.
