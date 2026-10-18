# Changes on `fix/sticky-filters`

- Filters are sticky for the session: a new search (origin, destination, stops, travel mode, accessibility, access,
  departure) no longer resets them; only the picked / chosen route resets.
- "Wyczyść filtry" in the filter sheet (was "Wyczyść") resets them.
- Transit-only filter chips (sort, vehicles, transfers, max walk) are hidden on street trips, but kept.
- Tests: `src/stickyFilters.test.tsx`.
