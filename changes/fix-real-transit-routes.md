# fix/real-transit-routes

- `POST /api/routes` uses `RealRouteEngine`: GTFS departures, one transfer, OSM walk/bike paths,
  live Veturilo docks. The fare is the cheapest matching row in `fare_attributes.txt`.
- The data app (`main.py`) also serves `/api/routes` and `/api/geocode`, with CORS. One process.
- GTFS cache now stores stop `zone`, trip headsign, wheelchair, shape id and shape distance.
  A route leg follows the GTFS shape between the stops.
- Bus/tram detection fills `direction` from the GTFS headsign and polls trams as well as buses.
- Alerts from mkuran `alerts.json` add the tag `Zmiana na trasie`. Trip-update delays and the PKP PLK
  feed are not applied (PLK key still pending; ZTM realtime trip ids only partly match GTFS).
- Transfers between stops use straight-line pairs under 450 m to choose the change, then an OSM walk
  for the leg that is shown. The all-pairs street matrix from the data report is not stored.
