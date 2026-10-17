# Changes on `feature/map-style-v2`

- Added a second map look (v2) next to the original one (v1). A layers button on the map switches between them; the choice is saved in the browser.
- v2: flat pastel vector basemap (OpenFreeMap tiles drawn by MapLibre GL inside Leaflet), own style in `src/map/styleV2.ts` with a light and a dark palette; more labels appear when zoomed in.
- v2: lavender accent, round floating buttons, round route markers, white "me" marker with a navigation arrow, round destination marker.
- Assumptions: v1 stays the default; no automatic fallback to v1 if the tile service is down; the route keeps the transport-mode colours (they match the chips in the panels) and only walking legs use the lavender accent; no new data (e.g. stations) on the map.
- New dependencies: `maplibre-gl`, `@maplibre/maplibre-gl-leaflet`.
- `AGENTS.md`: project knowledge updated (map variants, style file, tile provider).
