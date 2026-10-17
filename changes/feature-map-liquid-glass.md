# feature/map-liquid-glass

- Second map look "liquid glass" (red + yellow, light and dark) next to the flat one. A layers button on the map switches between them; the choice is remembered (`map-look`). Default stays flat.
- Glass map: glowing roads, glass building tiles with a bright edge and soft shadow, light water shore; round map buttons and markers in frosted glass (blur); slowly drifting light over the map and a pulse on the location / destination markers (disabled with `prefers-reduced-motion`).
- `mapStyle.ts`: labels moved to `labelLayers` and shared by both looks; new `createGlassStyle`. New `map/palette.ts` `GLASS`, `map/glass.ts`, `map/glass.css`, `map/mapLook.ts`.
- Assumptions: no 3D buildings (the Leaflet + MapLibre layer cannot tilt), depth comes from shadows and edges instead; only the map, its buttons and markers are glass, not the cards and sheets.
