# fix/vehicle-popup

- The "W jakim pojeździe jesteś?" window no longer opens by itself when nothing was detected (no candidates, no location,
  live data unavailable, offline). The bus button on the map still opens it, with an explanation.
- One confident vehicle (`isConfident`: top-1 RMSE <= 60 m, 2nd >= 2.5x worse) shows a small bar
  "Wykryto linię 131 → Sadyba"; a tap opens the full sheet. Several plausible vehicles: the sheet in the middle, as before.
- Rule tuned on `data/live/bus_track_sample.json` (simulated riders and standing pedestrians), explained in
  `src/utils/vehicleConfidence.ts`.
- Tests: `vehicleConfidence.test.ts`, `vehiclePopup.test.tsx` (App: none / bar / sheet / 503 / offline / no location).
