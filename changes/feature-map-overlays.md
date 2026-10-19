# feature/map-overlays

- Map overlays switched from a new button in the right map bar: Veturilo stations (live bike count), bus + tram
  posts, metro + rail; only for the visible area, stops from zoom 14, Veturilo from zoom 13; remembered on the device.
- Popup on a station: name, post code, Veturilo bikes / free docks, "Stąd" / "Dotąd" fill the search.
- Frontend only: uses `GET /api/stations` and `GET /api/veturilo/status` (no API change).
