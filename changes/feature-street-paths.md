# feature/street-paths

Follow-up of `feature/street-matrix` (PR #55).

- Paths: `street_matrix <graph> --route I J [--route I J ...]` prints one JSON line per route: the path as
  `[lon, lat]` (5 decimals, ~1 m), distance, wait, the elevators boarded and the metro entrances used.
  Path recording is only on in this mode, so the matrix run does not pay for it.
- Graph file `SMG2`: node coordinates and edge flags (elevator, pushed bike, access segment, metro entrance).
  `preprocess_street.py --graph-only` writes only the graphs (~10 s), enough for `--route`.
- Code layout: `algorithms/street_model.py` (cost model), `algorithms/street_graph.py` (`StreetGraph` + file
  format), `osm.points_graph()` returns a `StreetGraph`. The scipy matrix engine (`--engine python`) is removed:
  the graph is built only in Python and searched only in C++ (plus `osm.route()` for arbitrary coordinates).
- Tests: `algorithms/test_street_model.py` checks the cost model and the C++ matrix / `--route` against a small
  scipy oracle. Graph files are byte-identical to before; `osm.route()` and `--route` agree.
