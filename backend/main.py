"""FastAPI app: data sources plus the route and geocode endpoints the frontend calls.

Run from backend/: uv run uvicorn main:app --reload
"""
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import bus_detect
from app.api import geocode, history
from app.api import routes as route_api
from app.config import settings
from config import DATA, MissingKey, UpstreamError, load_json
from sources import mkuran, nextbike, osm, um_warszawa
from sources.registry import SOURCES


log = logging.getLogger("main")

# Users never trigger heavy work. The server loads the GTFS and OSM caches once at start, in a
# background thread. While that runs, the endpoints that need them answer 503. The event starts
# set, so scripts and tests that import the app (without the lifespan) are not blocked.
READY = threading.Event()
READY.set()
NEEDS_CACHES = ("/api/gtfs", "/api/osm", "/api/routes", "/api/live/nearest-buses")


def _warm_up() -> None:
    try:
        mkuran.warm()
        osm.warm()
    except Exception:
        log.exception("cache warm-up failed; endpoints will try to build the caches on demand")
    finally:
        READY.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    READY.clear()
    threading.Thread(target=_warm_up, daemon=True, name="cache-warmup").start()
    bus_detect.start_poller()
    yield


app = FastAPI(lifespan=lifespan, title="WarsawOpenData data API",
              description="GTFS, City Hall, Veturilo, OSM, and route options from that data. "
                          "No database: files in data/, parsed on first use.")


@app.middleware("http")
async def wait_for_caches(request: Request, call_next):
    if not READY.is_set() and request.url.path.startswith(NEEDS_CACHES):
        return JSONResponse({"detail": "cache is loading, try again in a minute"}, status_code=503,
                            headers={"Retry-After": "30"})
    return await call_next(request)


@app.exception_handler(httpx.HTTPError)
@app.exception_handler(UpstreamError)
async def upstream_failed(request: Request, exc: Exception):
    # The detail goes to the log only: httpx messages contain the full URL, with the api key.
    log.warning("upstream call failed for %s: %s", request.url.path, exc)
    return JSONResponse({"detail": "external data source failed, try again later"}, status_code=502)


@app.exception_handler(MissingKey)
async def key_missing(request: Request, exc: MissingKey):
    return JSONResponse({"detail": str(exc)}, status_code=503)


@app.exception_handler(FileNotFoundError)
async def file_missing(request: Request, exc: FileNotFoundError):
    name = Path(exc.filename).name if exc.filename else "data file"
    return JSONResponse({"detail": f"{name} is missing: run download.py (or report.py for /api/stats)"},
                        status_code=404)


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
