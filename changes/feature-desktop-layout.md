# feature/desktop-layout

- Wide screens (from 600 px): a side panel on the left (360 px, 420 px from 900 px), full height and scrollable, with the
  search card on top and the vehicle window / route list / route details / active trip below it. No draggable sheets there:
  `SnapSheet` renders plain cards when docked (`SheetDock` context), the "Wybierz tę trasę" button stays at the panel bottom.
- The map starts right of the panel, so a route is never under it; the map buttons stay on the right; the bottom bar sits
  under the panel only.
- Phones (< 600 px): unchanged.
- Test: `src/desktopLayout.test.tsx` (1440 px: search + list in one panel, no drag handles, details in the panel; 430 px: the sheets).
