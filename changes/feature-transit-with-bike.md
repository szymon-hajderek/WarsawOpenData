# feature/transit-with-bike

- Contract (`data/API.md`): `POST /api/routes` takes `access` = `walk` (default) | `bike` for transit trips.
- Backend: `access: "bike"` plans with the router's `/plan` in mode `bike` (own bike to, from and between stops,
  carried on transit; no Veturilo); `excludeModes` still applies; `bikeKmh` 0 keeps the default bike speed.
  Titles name the ridden bike legs ("Rower + 525 + Rower"); the street-only trip is "Własny rower" (id `bike`).
  422 when combined with a wheelchair / stroller.
- Frontend: "Dojazd: Pieszo | Rowerem" under Komunikacja (`TransitAccessToggle.tsx`); Rowerem hides the
  accessibility toggle and sends `access: "bike"` with profile `standard`.
- Tests: `backend/tests/test_transit_bike_access.py`, `frontend/src/transitAccess.test.tsx`.
