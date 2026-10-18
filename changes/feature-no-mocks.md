# feature/no-mocks

- Frontend: removed the in-browser route mock (`mockRouteOptions`, `mockMultiStop`, templates, `api/multiStop.ts`,
  `buildPath` / `slicePath` in `utils/geo.ts`) and the vehicle mock (`POOL`, `mockCandidates`).
- `VITE_API_URL=""` now means "backend off": routes and vehicle detection take the same offline path as an
  unreachable backend ("Nie połączono z serwerem"). `MAX_STOPS` moved to `api/routes.ts`.
- Removed the `mock` flags (hooks, `RouteResult`, `DetectionResult`, `JourneySelection`), the "Dane przykładowe" chip,
  the one-time snackbar and the mock handling in `DemoPage` / `HistoryProvider`.
- Kept: place search offline list / Nominatim fallback, the local speed summary.
- Backend: deleted `app/routing/stub_engine.py` and the `stub` branch of `ROUTE_ENGINE`.
- Tests: new `api/noBackend.test.ts` (empty `API_URL` -> offline error, no request, no data); mock tests removed.
- Docs: AGENTS.md, README.md, frontend/README.md, backend/README.md.
