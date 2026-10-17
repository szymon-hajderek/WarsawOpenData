"""GET /api/stations: the StationLocations overlay (stations.json), the same file the C++ router loads.
Positions are OSM where an exact match exists, else GTFS; ids are the mkuran ids. Contract: data/API.md."""
from fastapi import APIRouter, HTTPException, Query

import stations
import street_router
from config import BBOX, in_bbox
from sources.mkuran import parse_bbox

router = APIRouter(prefix="/api/stations", tags=["Stations (StationLocations overlay)"])
KINDS = ("bus_post", "tram_post", "metro_platform", "rail_platform", "rail_station", "veturilo")


@router.get("")
def api_stations(kind: str | None = Query(None, description="|".join(KINDS)),
                 feed: str | None = Query(None, description="ztm, pkp, wkd, nextbike"),
                 source: str | None = Query(None, description="osm or gtfs (where the position comes from)"),
                 bbox: str | None = Query(None, description="min_lat,min_lon,max_lat,max_lon")):
    """Transport nodes (posts, platforms, stations, Veturilo) with one position each: OSM when an exact match exists,
    else GTFS. The list the router, the matrices and the frontend share."""
    if kind and kind not in KINDS:
        raise HTTPException(422, f"kind must be one of {', '.join(KINDS)}")
    box = parse_bbox(bbox) if bbox else BBOX
    return [l for l in stations.locations()
            if (not kind or l["kind"] == kind) and (not feed or l["feed"] == feed)
            and (not source or l["source"] == source) and in_bbox(l["position"]["lat"], l["position"]["lon"], box)]


@router.get("/report")
def api_report():
    """How the overlay was matched to OSM: counts per kind, posts whose ref is too far away, hash."""
    rep = stations.load()
    return {"hash": rep["hash"], "built": rep["built"], **stations.load_json(stations.REPORT)}


@router.get("/health")
def api_health():
    """The router's view: loaded modes, the overlay it serves, and whether the stop-to-stop matrices belong to it
    (`matrices.status`: ok | stale | missing). 503 when the router is not running."""
    return street_router.health()


@router.get("/{station_id}")
def api_station(station_id: str):
    """One location by its id (e.g. ztm:435102, ztm:7014M:P1, pkp:33506_P2, vet:203610)."""
    for l in stations.locations():
        if l["id"] == station_id:
            return l
    raise HTTPException(404, "unknown station id (use the mkuran id, e.g. ztm:700901)")
