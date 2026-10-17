# Changes on `feature/route-sheets-snap`

- New shared `SnapSheet` (`src/components/SnapSheet.tsx`): the 3-height draggable panel of the vehicle popup (bar, middle, full) as one reusable component with a header (drag zone), a pinned toolbar and footer, and scrolling content. Same gestures: follows the finger, a flick skips a level, a tap steps up, Enter / arrow keys work.
- The route list ("Wybierz trasę") and the route details use it. List: bar = number of routes and the fastest; middle = header, the pinned filters row, the selected route and the pinned "Wybierz tę trasę"; full = all routes. Details: bar = title, duration, distance and times; middle = start / destination, the leg bar and time / distance; full = all tiles, the trip recorder and the steps ("Przebieg trasy" is no longer collapsible). The selected route is scrolled into view when the list is below full height.
- `VehicleSheet` now uses `SnapSheet` (behaviour unchanged). `Sheet.tsx` was removed.
- `App.tsx`: `optionsSnap` / `detailsSnap` replace `stepsExpanded` (both start in the middle when the screen changes); the map padding follows the current sheet height so the route stays visible above it.
- Assumptions: middle heights are 258 px (vehicle popup), 352 px (list) and 292 px (details), always at most half of the screen; bar 76 px; full 62% of the screen (the screen minus 200 px on wide screens).
- `AGENTS.md` updated. No new dependencies, so the `README.md` setup is unchanged.
