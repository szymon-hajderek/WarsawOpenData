# feature/map-3d-prototype

A prototype, on purpose easy to remove: a tilted 3D map as an option.

- New button "3D" (`Włącz mapę 3D (prototyp)`) in the map controls. It switches to `MapView3D`, a separate map drawn with MapLibre GL directly: pitch 55, a slight turn, buildings extruded from the tile data (`render_height`), light and dark, flat and glass look. Buttons in 3D: 2D (back), theme, location, zoom, tilt on / off.
- `map/style3d.ts` (`with3dBuildings`, tested): replaces the flat building layers with one `fill-extrusion` layer under the labels and adds a light. `map/route3d.ts` (`routeGeoJson`, tested): the route lines as GeoJSON, one per leg part (ridden solid, pushed dashed, walking dotted, steps / elevators). `map/map3d.ts`: remembered switch.
- `App` loads `MapView3D` lazily (MapLibre GL is not in the main bundle for 2D users).
- Not in 3D (use 2D): picking a point on the map (picking switches back to 2D), the stops of the chosen route, popups of the stop layers, the follow mode of an active trip.
- Assumptions: pitch 55 and bearing -17 look good on a phone; building colours are lighter than the flat ones so the walls read; no new dependency (`maplibre-gl` was already there).
- Checked in the browser pane (WebGL works there): light and dark, buildings and the tilt; route lines checked only in unit tests until the backend is up again.
- The 2D / 3D switch is the first button of the map controls in both maps, so it stays at the same place (checked: same position in 2D and 3D).
- Second round (user feedback): the + and - zoom buttons are removed from both maps; both maps now share one `MapControls` component, so the buttons are the same and in the same order (2D / 3D, theme, look, stop layers, vehicle detection, my location); the 3D map has the look switch and the stop layers (Veturilo pills with bike counts, dots for stops; `useMapOverlays` now works with both maps); new rotate mode in 3D: one finger turns and tilts the map (pan is off while it is on), two-finger rotate / tilt of MapLibre stays on.
- Checked in the browser pane: the same six buttons at the same heights in 2D and 3D (3D has the rotate button below), stop layers visible in 3D, a drag in rotate mode turns the map.
- Third round: the look (flat / glass) button is removed from the map controls (one button less, so the rotate button of the 3D map no longer sits under the vehicle bar). The look is now a setting in Preferences, new section "Widok" (`ViewSection`); `useMapLook` is one shared value (`useSyncExternalStore`), so both maps follow a change made there. Checked in the browser pane: Widok section, 5 shared buttons + rotate, switching to Szklana restyles the map.
- Note: `src/routeList.test.tsx` (sticky filters, a teammate's test) takes about 5 s and fails when the whole suite runs under load; it passes alone.
