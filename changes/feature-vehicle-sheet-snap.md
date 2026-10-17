# Changes on `feature/vehicle-sheet-snap`

- The "W jakim pojeździe jesteś?" popup is no longer on / off: it follows the finger and settles on three heights (`VehicleSnap`): `bar`, `middle` (title, suggested line, "Jadę tą linią"; about a third of the screen) and `full` (other lines, "Inna linia", "Wykryj ponownie", "Nie jadę komunikacją"). A quick flick skips a level, a tap steps up (and from `full` back to `middle`), Enter / Space / arrow keys work too, and the part below the visible height is `inert`.
- The popup now starts in the middle instead of fully open, so it no longer takes a large part of the screen; confirming a line collapses it to the bar, the map bus button and "Wykryj ponownie" reopen it in the middle.
- `App.tsx`: state `vehicleSnap` instead of the `vehicleOpen` boolean.
- Assumptions: snap heights are a bar of 76 px, a middle of about 258 px (at most half of the screen) and a full of 62% of the screen (the screen minus 200 px on wide screens); dragging works on the handle and header (the content scrolls in the full state).
- `AGENTS.md`: popup paragraph updated. No new dependencies, so the `README.md` setup is unchanged.
