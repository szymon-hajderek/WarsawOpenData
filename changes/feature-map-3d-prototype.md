# feature/map-3d-prototype

A prototype, on purpose easy to remove: a tilted 3D map as an option.

- New button "3D" (`Włącz mapę 3D (prototyp)`) in the map controls. It switches to `MapView3D`, a separate map drawn with MapLibre GL directly: pitch 55, a slight turn, buildings extruded from the tile data (`render_height`), light and dark, flat and glass look. Buttons in 3D: 2D (back), theme, location, zoom, tilt on / off.
- `map/style3d.ts` (`with3dBuildings`, tested): replaces the flat building layers with one `fill-extrusion` layer under the labels and adds a light. `map/route3d.ts` (`routeGeoJson`, tested): the route lines as GeoJSON, one per leg part (ridden solid, pushed dashed, walking dotted, steps / elevators). `map/map3d.ts`: remembered switch.
- `App` loads `MapView3D` lazily (MapLibre GL is not in the main bundle for 2D users).
- Not in 3D (use 2D): picking a point on the map (picking switches back to 2D), stop overlays and popups, the follow mode of an active trip, the Veturilo / overlay layers button.
- Assumptions: pitch 55 and bearing -17 look good on a phone; building colours are lighter than the flat ones so the walls read; no new dependency (`maplibre-gl` was already there).
- Checked in the browser pane (WebGL works there): light and dark, buildings and the tilt; route lines checked only in unit tests until the backend is up again.
