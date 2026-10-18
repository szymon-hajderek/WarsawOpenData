# feature/exclude-modes-ui

- Preferences: new persistent "Środki transportu" section (`Preferences.excludedModes`: bus, tram, metro, rail,
  veturilo; `TransportModesSection`), stored with the preferences, shown in the "Zaawansowane" filters, and time rules
  can override it (`excludedModes` override).
- FilterSheet: the vehicle chips start from the preference and override it for the current search only
  (`TripFilters.modes`, null = as in the preferences).
- Request: `routeSearchBody(trip, filters.modes)` sends both as `excludeModes` to `POST /api/routes`.
- `applyListFilters` no longer filters by mode (the backend does it); max walking time stays client-side.
- Tests: `preferences/excludeModes.test.ts`.
- Needs the backend `excludeModes` field (parallel backend PR); until then the backend ignores it.
