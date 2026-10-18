# Changes on `fix/sticky-filters`

- Filters are sticky for the session: a new search (origin, destination, stops, travel mode, accessibility, access,
  departure) no longer resets them; only the picked / chosen route resets.
- "Wyczyść filtry" in the filter sheet (was "Wyczyść") resets them.
- Transit-only filter chips (sort, vehicles, transfers, max walk) are hidden on street trips, but kept.
- "Odśwież trasy" button in the route list header (phone sheet and desktop panel): runs the same search again
  ("Teraz" = a new now, a chosen time stays), keeps the selected route when its id is still there, spinner while loading.
- Tests: `src/routeList.test.tsx`.
- Found and reported (not fixed): #118, duplicate option ids from the route engine.
