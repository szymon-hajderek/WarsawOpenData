"""FastAPI app: data sources plus the route and geocode endpoints the frontend calls.

Run from backend/: uv run uvicorn main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import bus_detect
from app.api import geocode, history
from app.api import routes as route_api
from app.config import settings
from config import load_json, DATA
from sources import mkuran, nextbike, osm, um_warszawa
from sources.registry import SOURCES


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus_detect.start_poller()
    yield


app = FastAPI(lifespan=lifespan, title="WarsawOpenData data API",
              description="GTFS, City Hall, Veturilo, OSM, and route options from that data. "
                          "No database: files in data/, parsed on first use.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
for module in (mkuran, um_warszawa, nextbike, osm):
    app.include_router(module.router)
app.include_router(bus_detect.router)
app.include_router(route_api.router)
app.include_router(geocode.router)
app.include_router(history.router)


@app.get("/api/sources", tags=["meta"])
def api_sources():
    """All data sources: URL, local file, key, license / attribution, status."""
    return SOURCES


@app.get("/api/stats", tags=["meta"])
def api_stats():
    """Vertex / edge counts from the last report run (backend/report.py)."""
    return load_json(DATA / "report.json")
