# feature/vehicle-after-route

- The bus button on the map and the vehicle window ("W jakim pojeździe jesteś?") now work after a route is found too: on the route list and on the route details. Before, both existed only in the search step and vanished once a destination was set.
- While the window is open in those steps it replaces the route sheet (no overlap); closing it with the bus button (or "Nie jadę komunikacją") brings the sheet back. Confirming a vehicle ("Jadę tą linią") closes the window and keeps the vehicle: a dot on the bus button shows it, and it is the vehicle an active trip starts with.
- The window that is found automatically at the start is closed when a route list appears, so it never covers the list. `useVehicleDetection` has a stable `hide()` (the window closes, the confirmed vehicle stays); `dismiss()` still forgets the vehicle.
- Not available in an active trip (its own detection) and while picking a point on the map.
- Checked in the browser pane (phone size) on the route details: click on the bus button shows the vehicle window instead of the details, the next click brings the details back. Confirming could not be tried there (no live vehicles without `PORTAL_KEY`); the hook is tested (`hide()` keeps the confirmed vehicle).
- Depends on PR #133 (the bus button as a toggle, `vehicleOpen`): merge it first.
