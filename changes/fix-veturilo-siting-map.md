# fix/veturilo-siting-map

Follow-up to `feature/veturilo-siting` (PR #70, merged before these commits landed).

- Map page `artifacts/veturilo-siting.html`: own canvas map (drag, wheel / buttons to zoom, click a hex) instead of
  Leaflet + OSM tiles. With Leaflet from the CDN the map stayed empty and the layer buttons did nothing when the script
  did not load; OSM tiles showed "Access blocked" for a page opened from disk.
- E-scooter data in the city's format: a crowding index 0..1 per 175 m hexagon (`data/mock/scooter_intensity.json`,
  replaces `scooter_events.json.gz`). E = mean of the city values per our hex, IDW for the rest. No scooter dots on the map.
