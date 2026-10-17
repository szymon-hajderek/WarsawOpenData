"""FastAPI app: mounts one router per data source. Run from backend/: uv run uvicorn main:app --reload"""
from fastapi import FastAPI

from config import load_json, DATA
from sources import mkuran, nextbike, osm, um_warszawa
from sources.registry import SOURCES

app = FastAPI(title="WarsawOpenData data API",
              description="Raw data from mkuran GTFS, um.warszawa.pl, Veturilo GBFS and OSM. No database: "
                          "files in data/, parsed on first use.")
for module in (mkuran, um_warszawa, nextbike, osm):
    app.include_router(module.router)


@app.get("/api/sources", tags=["meta"])
def api_sources():
    """All data sources: URL, local file, key, license / attribution, status."""
    return SOURCES


@app.get("/api/stats", tags=["meta"])
def api_stats():
    """Vertex / edge counts from the last report run (backend/report.py)."""
    return load_json(DATA / "report.json")
