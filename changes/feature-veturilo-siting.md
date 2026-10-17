# feature/veturilo-siting

Where to put new Veturilo stations.

- `algorithms/station_siting.py` (+ tests): hex grid (axial, 175 m), point in polygon, P(d), J_synergy, per-hex means, IDW,
  normalisation, greedy picking with a distance update after every pick.
- `backend/sources/siting.py`: Warsaw boundary from Nominatim, S from OSM tags (one osmium pass), mock traffic counters and
  e-scooter events, d_net by multi-source Dijkstra on the bike graph, cached hex table, `GET /api/veturilo/siting`, `warm()`.
- `backend/siting_report.py`: trial report `data/SITING_REPORT.md` + `data/siting_report.json` + map page
  `artifacts/veturilo-siting.html` (layers T / E / S / d_net / J, mock points, greedy step slider).
- Committed data: `data/geojson/warsaw.geojson`, `data/mock/traffic_counts.json`, `data/mock/scooter_events.json.gz` (MOCK).

Assumptions (decided while building):
- E is normalised on log(1 + count) because the scooter counts are heavy-tailed (hotspots).
- d_net is measured from the station to the hex (directed bike graph, riding + pushing), plus the hex centre's snap distance.
- A hex without any street segment gets S = 0.3 but is never a candidate anyway.
- The endpoint returns the plain ranking list; `dNet` is `null` beyond 5000 m.
