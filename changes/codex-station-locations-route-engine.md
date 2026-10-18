# Station-aware route planning (#79)

- Use copied StationLocations positions and station IDs throughout transit and Veturilo planning.
- Rank boarding and alighting candidates through directional router access searches.
- Convert every street leg with one adapter, preserving optional segments, ride/push distances and mapped endpoints.
- Add nullable endpoint IDs and optional segments to the API contract, backend models and frontend validation.
- Add stroller profiles and explicit street-only travel modes to POST /api/routes; honor effective speeds and accessibility.
- Skip missing street paths and return 503 for router downtime instead of inventing straight lines.
- Keep transfer candidate discovery for the POC; actual transfer legs follow routed streets.
- Existing dependencies and setup commands remain unchanged; C++ verification runs in WSL with GCC 14.
- Validation: 238 backend/algorithm tests including C++; frontend lint, 74 tests and build; real local HTTP
  routes for walk, accessible, stroller, own bike and M1, with matching station endpoints and 422/503 errors.
- Missing transit geometry no longer drops a ride: `_ride_path` tries `mkuran.shape_slice`, then
  `mkuran.shape_by_stops` (WKD, merged from main #86), else a polyline through every call at its mapped position.
- New optional `RouteLeg.approximatePath` (API.md, models, frontend type + validation): true only for that polyline.
- `_street_tags`: "bez schodów" for accessible; stroller gets "schody tylko z rynnami" when the path has steps.
- `_by_street`: falls back to the 8 nearest candidates by straight line when `/access` reaches none of them.
- AGENTS.md: the C++ router never returns transit shapes; geometry comes from GTFS in `real_engine`.
