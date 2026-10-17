# Changes on `fix/react-review-frontend`

Fixes from a React review of `frontend/` (hooks, accessibility, error handling, performance).

- **Errors:** `ErrorBoundary` around the app; backend answers are checked (`src/api/validate.ts`); `.catch` and an error text in the route list.
- **Example data is marked:** a snackbar once and a "Dane przykładowe" chip on the route list and the vehicle window when the mock is used.
- **One backend URL:** `apiUrl(path)` in `src/config.ts` for routes, geocode, history and vehicle detection (the vehicle call used a different path before).
- **Geolocation:** `useLocationTrack` replaces the module-level `watchPosition` + `setInterval` (no leak, one stream, cleanup on unmount).
- **App.tsx** split into hooks `useRouteSearch` and `useVehicleDetection`; selection and step are derived while rendering; no ref write during render.
- **Accessibility:** cards use `pressableProps` (Space does not scroll); map and panels are `inert` under the Preferences page. (The sheet handle and the steps button from the review were replaced by `SnapSheet` on `main`, which already has keyboard support.)
- **Performance:** geocode and route requests are cancelled with `AbortController`; transfer marker icons are memoised; one MapLibre layer with `setStyle` on theme change; `react-dom/server` removed from the bundle (SVG paths in `ICON_PATH`); the preferences context changes only when the active time rule changes.
- **Smaller fixes:** `PlaceField` resets its text on blur; `LevelSelector` syncs while rendering (no effect); stable keys for legs; `MAP_PADDING` in `layout.ts`; `useColorMode` throws outside its provider.
- **Tooling:** ESLint (`npm run lint`) and Vitest + Testing Library (`npm test`, 14 tests). `README.md` and `AGENTS.md` updated.
- Assumptions: `usePreferences` / `useHistory` keep their default context values (tests and the app mount the providers anyway); `data/API.md` is unchanged (no API change); the old `eslint-disable` for `exhaustive-deps` stays only where the dependency is intentionally left out (`App.tsx` `via`, `useVehicleDetection`, `MapController`).
