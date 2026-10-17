# Changes on `feature/project-structure`

- Added empty top-level folders (kept in git via `.gitkeep`):
  - `frontend/` - React + TypeScript + Vite, Leaflet + OpenStreetMap map
  - `backend/` - Python + FastAPI
  - `algorithms/` - algorithms (mandatory folder)
  - `db/` - PostgreSQL + PostGIS (SQLite is enough for the POC)
  - `routing/` - OpenTripPlanner config
  - `data/` - datasets, one subfolder per data type: `gtfs/`, `gbfs/`, `osm/`, `geojson/`
- No code yet, structure only. Docker files (`docker-compose.yml`) will be added at the repo root later.
