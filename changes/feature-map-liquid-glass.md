# feature/map-liquid-glass

- Second map look "liquid glass" (red + yellow, light and dark) next to the flat one. A layers button on the map switches between them; the choice is remembered (`map-look`). Default stays flat.
- Glass map: glowing roads, glass building tiles with a bright edge and soft shadow, light water shore; round map buttons and markers in frosted glass (blur); slowly drifting light over the map and a pulse on the location / destination markers (disabled with `prefers-reduced-motion`).
- `mapStyle.ts`: labels moved to `labelLayers` and shared by both looks; new `createGlassStyle`. New `map/palette.ts` `GLASS`, `map/glass.ts`, `map/glass.css`, `map/mapLook.ts`.
- Assumptions: no 3D buildings (the Leaflet + MapLibre layer cannot tilt), depth comes from shadows and edges instead; only the map, its buttons and markers are glass, not the cards and sheets.
- Second pass (sharper, more glowing): saturated colours (red glass buildings, hot amber roads in light mode, neon red / yellow roads at night), wider blurred glow, light on water shores; motion: the road and shore glow "breathes" (paint opacity animated, about 20 fps), two bright bands sweep over the map, glints twinkle, a light runs around the rim of round buttons and markers (`@property --glass-angle`). All motion is off with `prefers-reduced-motion`.
- Third pass: night look redone (deep plum background, warm gold main roads, soft translucent minor roads, glass buildings, blue glass water) because the neon version was too harsh; day look only slightly tuned (calmer parks, lighter red glass buildings).
