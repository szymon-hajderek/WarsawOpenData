# fix/mobile-ui

- Phone: the route list no longer disappears ~6 s after a search. The automatic vehicle detection (every 5 s) reopened
  the vehicle window in place of the route sheet; now its collapsed bar floats above the route sheet / route details
  (`bottomOffset` on `SnapSheet` / `VehicleSheet`), and only an expanded window (or the bus button) replaces the sheet.
- Phone: the folded search card also shows the travel mode chips (Komunikacja / Pieszo / Rower) and, for Komunikacja,
  "Z własnym rowerem" (they were hidden behind the chevron); the map buttons start below it.
