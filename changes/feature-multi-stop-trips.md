# Changes on `feature/multi-stop-trips`

- Trips can have up to 5 intermediate stops. The search card has "Dodaj przystanek"; each stop has its own field, move up / down arrows (only in "Moja kolejność"), a remove button and a numbered dot on the gradient line. With 2 or more stops the chips "Moja kolejność" / "Optymalna" appear; the swap button reverses the whole trip (start <-> destination, stops in reverse).
- "Optymalna" reorders only the intermediate stops for the shortest trip; start and destination stay fixed (`algorithms/stop_order.py`, exact for up to 7 stops, with tests).
- Backend: `POST /api/routes` accepts `via` (max 5, else 422) and `order` (`given` | `optimal`); `RouteOption.waypoints` and `RouteLeg.stop` describe the result. `backend/app/routing/multi.py` plans each segment with the existing engine and chains the n-th best options (up to 3). Tests in `backend/tests/test_multi_stop.py`.
- Frontend: `fetchRouteOptions` takes one object (`from`, `to`, `profile`, `via`, `order`); the local mock does the same chaining (`src/api/multiStop.ts`). Numbered stop markers on the map, stop rows between legs in the route steps, "N przystanki" in the route list and the route header.
- Assumptions: no time spent at a stop; every segment is planned as if it starts now (the real engine has no start-time input yet); "optimal" uses straight-line distance; the chained options may repeat the best option of a segment that has fewer alternatives; the filters reset when the stops change.
- `AGENTS.md` and `README.md` (test command) updated. No new dependencies.
