# feature/heading-arrow

- The "me" arrow on the map now points where the user faces (it was always pointing north).
- Source: the compass when the device has one (Android `deviceorientationabsolute`, iOS `webkitCompassHeading`,
  permission asked on the first tap on iOS); otherwise the direction of the last 3 GPS fixes that are farther
  apart than the GPS error (10-30 m), so standing still never turns it. No direction known = a dot instead of the arrow.
- Not noisy: the compass is smoothed (unit-vector EMA), updates only by >= 3 degrees and at most every 150 ms,
  and the CSS rotation takes the shortest turn (no spin through north). A compass silent for 2 s falls back to movement.
- Both maps: `MapView` (Leaflet) and `MapView3D` (minus the map's own rotation).
- Code: `src/utils/heading.ts` (pure, tested), `src/hooks/useHeading.ts`, `src/map/userArrow.ts`, `moveHeading` in `useLocationTrack`.
