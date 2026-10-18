# feature/route-leg-delays

Live delay of the buses and trams in suggested routes, shown on the route list before the user boards.

- `algorithms/route_delays.py` (+ tests): trip ids from a transit option id (`pt-<trip>-<trip>`), split only where `-`
  starts a new feed prefix; per ride: GTFS line + brigade -> live vehicle id.
- `backend/bus_detect.py`: `POST /api/live/route-delays` (`data/API.md`), reusing the `/delay` estimate (`_delay_for`).
  A vehicle still on an earlier trip of its brigade gives its current delay with `sameTrip: false`.
- Frontend: `api/routeDelays.ts` (`apiUrl`, validator `isRouteDelays`, `{}` on mock / error), `hooks/useRouteDelays.ts`
  (refresh every 30 s), `LegChain` shows the delay after the line chip, `RouteOptionsSheet` hides the engine's
  "opóźnienie N min" tag when our delays are shown.

Assumptions / limits: the route engine is not changed, so this depends on the option id format of `real_engine.py`;
trips with intermediate stops (`multi-N` ids) get no delays; metro and trains show nothing (no live positions).
Not verified here: frontend lint / test / build (no Node on this machine) and a full route search (the C++ street
router is not built on this machine); the endpoint was checked against the live feed with real trip ids.
