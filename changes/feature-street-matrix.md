# feature/street-matrix

- Street matrix preprocess: `distance_m` + `wait_s` for every ordered pair of stops (`mkuran.vertices()`) and
  Veturilo stations, for `walk`, `bike` and `accessible`, on the full OSM graph. Python prepares the graph
  (`backend/preprocess_street.py`), the C++23 program `algorithms/router/preprocess/street_matrix` runs the
  all-pairs Dijkstra (~3.5 min per mode on 16 threads; the scipy version took ~1 h). Output in
  `data/derived/street/` (git-ignored). Docs: `algorithms/router/preprocess/README.md`.
- OSM map: Geofabrik `mazowieckie` instead of BBBike (all ZTM stops are now on the graph), cut on download
  to the ZTM bbox and the used tags: `data/osm/warsaw_ztm.osm.pbf`, 31 MB instead of 300 MB. Graph build ~17 s.
- Signal waits are paid once per junction (signal nodes < 30 m apart by path + the nodes between them).
  The wait is per edge (`osm.edges()`).
- A point joins the graph through up to 6 nearest nodes of the main component (virtual out / in nodes =
  multi-source Dijkstra with start costs). Access segments are walked; a bike is pushed.
- Bike can be pushed (walking speed, accessible graph) where riding is not allowed; extra time in `wait_s`.
- New mode `accessible`: no steps, uses elevators (60 s each). `/api/osm/route?mode=accessible`.
- Metro platforms join through all entrances of their station (GTFS `location_type=2`), 120 s + the mode's
  elevator wait (every entrance is assumed to have an elevator).
- `/api/osm/route` uses the same code: `length_m` includes the access segments, `wait_s` the new waits.
- Checks: pytest (incl. C++ vs Python on a small graph); 100 stop-level pairs vs `osm.route()` (max diff
  0.05 m / 0.05 s) and vs OSM platform nodes (`ref` = ZTM stop id); report section 5.
- Docs: `data/API.md`, `README.md` setup, `AGENTS.md`, `sources/registry.py`.
- Assumptions: output not committed; a self pair = 0; constants (2 min metro, 60 s elevator) are estimates.
- Paths: `street_matrix <graph> --route I J` prints the path (`[lon, lat]`, ~1 m precision), the elevators and the
  metro entrances used, as JSON lines. Path recording is off in the matrix run. Graph file `SMG2` (node coordinates,
  edge flags); `preprocess_street.py --graph-only` writes just the graphs.
