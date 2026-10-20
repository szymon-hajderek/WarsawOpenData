# feature/heading-arrow

- The "me" arrow on the map now points where the user faces (it was always pointing north).
- Source: the compass when the device has one (Android `deviceorientationabsolute`, iOS `webkitCompassHeading`,
  permission asked on the first tap on iOS); otherwise the direction of the last 3 GPS fixes that are farther
  apart than the GPS error (10-30 m), so standing still never turns it. No direction known = a dot instead of the arrow.
- Movement fallback is strict: fixes worse than 30 m are ignored (coarse first fix, Wi-Fi location), fixes older than
  60 s are forgotten, no new fix for 30 s (standing) = a dot again, a zigzag of 3 fixes is drift, not a direction.
- Not noisy: the compass is smoothed (time-based unit-vector EMA, tau 200 ms), updates only by >= 3 degrees and at most
  every 150 ms (the last reading still shown after a pause), and the CSS rotation takes the shortest turn. The compass
  stays while the phone lies still (no events then). iOS permission asked on the first click / touchend (capture phase).
- The compass hook lives in the marker (`UserMarker`, `MapView3D`), so its updates do not re-render the whole app.
- Both maps: `MapView` (Leaflet) and `MapView3D` (minus the map's own rotation).
- Code: `src/utils/heading.ts` (pure, tested), `src/hooks/useHeading.ts`, `src/map/userArrow.ts`, `moveHeading` in `useLocationTrack`.
