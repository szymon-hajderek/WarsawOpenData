# feature/backend-offline-message

- When the backend is switched on (`VITE_API_URL` set, default `http://localhost:8000`) but does not answer, the app no longer shows made-up routes and vehicles. It says **"Nie połączono z serwerem. Sprawdź, czy backend działa."** in a red snackbar, in the route list and in the vehicle window (with "Spróbuj ponownie").
- Counts as not connected: a network error, a 5xx answer, or an answer of the wrong shape. A 4xx (the backend refused the query, e.g. a point outside Warsaw) keeps the generic "Nie udało się pobrać tras".
- Example data ("Dane przykładowe") remains only for the explicit offline mode `VITE_API_URL=""`.
- Code: `BackendOfflineError` in `api/routes.ts`; `useRouteSearch` and `useVehicleDetection` expose `offline`; `detectVehicle` returns `offline`; `RouteOptionsSheet` / `VehicleSheet` get an `offline` prop; `App.tsx` shows the snackbar.
- Assumptions: no location -> the vehicle window shows nothing instead of an example vehicle; the place search is unchanged (it still answers from the bundled list when the backend is down); history summary and delay keep their own quiet fallbacks.
- Side effect: without a running backend the app now has no routes at all (before it showed examples). Use `VITE_API_URL=""` for UI work without a backend.
