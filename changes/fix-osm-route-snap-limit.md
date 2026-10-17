# fix/osm-route-snap-limit

- `GET /api/osm/route` returns `422` when the start or the end is more than 1000 m from the street graph
  (`MAX_SNAP_M` in `backend/sources/osm.py`). Before, a point outside Warsaw snapped to the graph edge and gave
  a 0-length route with a huge `snap_m`.
- The check runs before Dijkstra. Error order: 400 bad `mode`, 422 too far, 404 no path.
- `/api/osm/nearest` and the Python functions `osm.route()` / `osm.nearest()` have no limit (`report.py` needs far snaps).
- `data/API.md` and `AGENTS.md` updated.
- `backend/uv.lock` needed no change: it already matches `pyproject.toml` on `main` (`uv lock --check` passes).
