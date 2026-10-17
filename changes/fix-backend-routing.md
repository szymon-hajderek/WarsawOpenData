# fix/backend-routing

- Live vehicle feed: no `PORTAL_KEY` means the poller stays off and `GET /api/live/vehicles` returns 503, without a traceback. With the key the poller calls the City Hall client directly instead of HTTP to itself.
- Route clock is Europe/Warsaw. Before 04:00 the search uses the previous GTFS service day (hours 24+). `POST /api/routes` accepts optional `when` (`HH:MM` or ISO).
- Boarding and alighting stops are one post per stop group, so one node cannot fill all 8 slots.
- Veturilo can sit in front of one direct ride, or after one, when a station with a bike and a station that accepts returns make that shorter. Drop-off requires `is_returning` and a free dock; a virtual station with returns counts as a dock.
- Bike price uses the GBFS `per_min_pricing` brackets when the pricing file loads, otherwise the previous hardcoded brackets.
- Still not in this branch: a second transfer, `transfers.txt` / station pathways, live delays, WKD/KM/SKM fares, and street time inside the search (OSM is still only for the options that are returned).
