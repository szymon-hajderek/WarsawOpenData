# feature/data-sources

Issue #18: data from all sources, parsers, endpoints and a data report.

- `backend/` uv project (`pyproject.toml`, `uv.lock`) with FastAPI app `main.py`.
- One module per source in `backend/sources/`: `mkuran.py` (GTFS ZTM + WKD + trains),
  `um_warszawa.py` (live vehicles, lines and times at a stop, route variants), `nextbike.py`
  (Veturilo GBFS), `osm.py` (walk and bike graph with expected waits at crossings).
- `download.py` fills `data/`; GTFS zips and the OSM extract go through Git LFS.
- Live sources: proxy endpoints with a 30 s cache plus one snapshot in `data/live/`.
- `report.py` writes `data/REPORT.md` (Mermaid source graph, ID compatibility, vertex and edge
  counts for items 1-4, endpoint list) and `data/report.json` (served at `/api/stats`).

Assumptions (decided during implementation):
- Signal waits: HCM average delay with a 90 s cycle, 20 s pedestrian green, 30 s road green;
  2 s at other crossings for walking. OSM in Warsaw has no timing tags.
- Speeds: walk 1.3 m/s, bike 4.2 m/s.
- Street routing snaps to the largest strongly connected component of each graph.
- Timetable reference day: the first Wednesday covered by all feeds.
- ZTM area = extent of ZTM stops (51.91-52.51 N, 20.57-21.48 E).
