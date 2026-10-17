# feature/veturilo-siting

Where to put new Veturilo stations.

- `algorithms/station_siting.py` (+ tests): hex grid (axial, 175 m), point in polygon, P(d), J_synergy, per-hex means, IDW,
  normalisation, greedy picking with a distance update after every pick.
- `backend/sources/siting.py`: Warsaw boundary from Nominatim, S from OSM tags (one osmium pass), mock traffic counters and
  e-scooter events, d_net by multi-source Dijkstra on the bike graph, cached hex table, `GET /api/veturilo/siting`, `warm()`.
- `backend/siting_report.py`: trial report `data/SITING_REPORT.md` + `data/siting_report.json` + map page
  `artifacts/veturilo-siting.html` (layers T / E / S / d_net / J, mock points, greedy step slider). The map is drawn on our
  own canvas (drag, wheel / buttons to zoom, click a hex); no Leaflet, no tiles, so it works offline and in the artifact viewer.
- Committed data: `data/geojson/warsaw.geojson`, `data/mock/traffic_counts.json`, `data/mock/scooter_intensity.json` (MOCK).
- E is in the city's format: a crowding index 0..1 per 175 m hexagon (no single scooter positions). The mock draws fake
  trips only in memory and saves the index per hexagon; the map shows it as layer E (no scooter dots).

Assumptions (decided while building):
- The mock index is log(1 + trips in the hex) scaled to 0..1, because trips are heavy-tailed (hotspots).
- The city grid is assumed to use the same 175 m hexagons; city values are averaged per our hex, so a shifted grid works too.
- d_net is measured from the station to the hex (directed bike graph, riding + pushing), plus the hex centre's snap distance.
- A hex without any street segment gets S = 0.3 but is never a candidate anyway.
- The endpoint returns the plain ranking list; `dNet` is `null` beyond 5000 m.
