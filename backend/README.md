# Backend

FastAPI app with data download and parsers. No database: raw files live in `../data/`.

```bash
cd backend
uv sync                              # install deps (Python 3.12, .venv)
uv run python download.py            # download all sources (or: download.py mkuran|um_warszawa|nextbike|osm)
uv run uvicorn main:app --reload     # API at http://localhost:8000, docs at /docs
uv run python report.py              # write ../data/REPORT.md and ../data/report.json
```

Keys come from `../.env` (`PORTAL_KEY`, `WAW_API_KEY`, see `../ACCESS.md`). Only the City Hall
endpoints need them.

The first call that needs GTFS or OSM builds caches in `../data/derived/` (~25 s and ~45 s).

See `../data/REPORT.md` for sources, ID compatibility, graph sizes and the full endpoint list.
