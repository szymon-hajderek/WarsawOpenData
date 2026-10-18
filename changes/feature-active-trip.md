# feature/active-trip

- Active trip mode: "Rozpocznij przejazd" (route details) enters it, "Zakończ" leaves it and saves the pace recording
  (recorder logic unchanged; it now exposes `tracker.track()`). `ActiveTripSheet`: next step, legs with the current one
  highlighted, "W jakim pojeździe jestem?", "Zmień cel", "Zakończ". The map follows the user (`MapView` `follow`).
- `src/utils/progress.ts` (+ tests): projection on the leg paths, forward only, current leg, next-step text,
  off-route (> 150 m) with "Zmień trasę". `useTripProgress` keeps the progress per route.
- Vehicle detection in the trip uses the trip's recorder points (`detectionPoints`: last 3, >= 8 s apart). The confirmed
  vehicle stays independent of the destination; "Nie jadę komunikacją" clears it.
- New destination / route: the full `SearchCard` with "← Wróć do przejazdu"; with a confirmed vehicle the start is
  "Z pojazdu: <line> (następne przystanki)" and `POST /api/routes` gets `onboard: {vehicleId}`; 404 -> GPS start + note.
  Choosing an option replaces the route of the active trip.
- Later departure: "Rozpocznij przejazd" opens a waiting state ("Wyjazd o 14:30 · za 23 min", first step, "Anuluj",
  "Ruszam teraz"); GPS progress, off-route checks and the recording start at the departure time or on "Ruszam teraz".
  Pure helper `src/utils/tripStart.ts` (+ tests). Without the departure-time picker the date is today.
- Tests: `src/activeTrip.test.tsx` (whole app, recorded bus-1002 track + GPS noise, answers per the contract),
  `src/utils/progress.test.ts`; fixtures in `src/test/busTrack.ts`, `src/test/tripFixtures.ts`.
- Needs the backend `onboard` field (parallel backend PR).
