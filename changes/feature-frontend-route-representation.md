# feature/frontend-route-representation

Frontend ready for the new route representation (backend: branch `feature/backend-leg-geometry`).

- Street-only trips (walk, wheelchair, stroller, own bike) now use `POST /api/routes` with `travel`
  (also with `via` / `order`) instead of `GET /api/osm/route`; the raw router parsing is gone.
  Polish error texts and the no-mock rule stay.
- Types and validation: `RouteLeg.elevators` / `steps` (`[lat, lon]`), `RouteLeg.waitS`, `RouteLeg.tripId`,
  `RouteOption.waitS`, all optional; wrong types are rejected.
- Map: elevator / steps icons come from `accessPoints(route)` (`src/utils/overlay.ts`), no coordinate swap.
- Waits in the UI: "czekasz N min" on transit steps in the route details, "w tym czekanie N min" next to
  the duration in the route list and the details header (only from 60 s).
- Mock fills `waitS` on legs and options; test fixtures re-recorded from `POST /api/routes`.
