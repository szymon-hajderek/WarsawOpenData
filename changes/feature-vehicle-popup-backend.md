# Changes on `feature/vehicle-popup-backend`

- Vehicle popup: "Inna linia" field (autocomplete over all live lines from the backend) adds a hand-picked card ("wybrana ręcznie", removable) that is confirmed with the same "Jadę tą linią" button.
- Re-detect buttons: "Wykryj ponownie" inside the popup and a round bus button on the map (start screen only); the map button also brings the popup back after "Nie jadę komunikacją".
- Direction: "kier." is hidden when the direction is empty (live buses have none yet).
- The suggested line shows how far the vehicle is ("ok. 120 m od Ciebie", from the backend's `rmse_m`).
- `detectVehicle()` now returns `{ candidates, lines }` and keeps `vehicleNo`, `brigade` and `distanceM` on the candidates (vehicle number and brigade are not shown yet).
- Assumptions: the map button exists only on the start screen (the popup is only shown there); re-detection clears the hand-picked line, a confirmed vehicle stays confirmed until the user changes it; manual cards use mode `bus` (the backend returns bus lines only); no backend changes.
- `AGENTS.md`: popup paragraph updated. No new dependencies, so the `README.md` setup is unchanged.
