"""Veturilo (Nextbike, system "nextbike_vw") from the public GBFS 2.x feed. No key needed.

station_id is Nextbike's own id; it has no link to GTFS ids. Stations join to transit stops and
the street graph only by location (nearest stop / nearest OSM node).
Alternative (more detail, non-standard): https://maps2.nextbike.net/maps/nextbike-live.json?city=812
"""
import httpx
from fastapi import APIRouter, HTTPException

from config import GBFS_DIR, TTLCache, load_json, save_json

BASE = "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_vw"
FILES = ["gbfs", "system_information", "vehicle_types", "station_information", "station_status",
         "free_bike_status", "system_pricing_plans", "system_regions", "geofencing_zones"]

_cache = TTLCache(30)


def _url(name: str) -> str:
    return f"{BASE}/gbfs.json" if name == "gbfs" else f"{BASE}/pl/{name}.json"


def fetch(name: str) -> dict:
    r = httpx.get(_url(name), timeout=30)
    r.raise_for_status()
    return r.json()


def download() -> list[str]:
    for name in FILES:
        save_json(GBFS_DIR / f"veturilo_{name}.json", fetch(name))
    return [f"veturilo_{n}.json" for n in FILES]


def _get(name: str, live: bool) -> dict:
    if live:
        return _cache.get(name, lambda: fetch(name))
    return load_json(GBFS_DIR / f"veturilo_{name}.json")


def stations(live: bool = False) -> list[dict]:
    """Station locations. Static data, so the saved file is the default."""
    return [{"id": f"vet:{s['station_id']}", "station_id": s["station_id"], "name": s["name"],
             "number": s.get("short_name"), "lat": s["lat"], "lon": s["lon"],
             "capacity": s.get("capacity"), "virtual": s.get("is_virtual_station", False)}
            for s in _get("station_information", live)["data"]["stations"]]


def status(live: bool = True) -> list[dict]:
    return [{"station_id": s["station_id"], "bikes": s["num_bikes_available"],
             "docks": s.get("num_docks_available"), "types": s.get("vehicle_types_available", []),
             "renting": s.get("is_renting"), "returning": s.get("is_returning")}
            for s in _get("station_status", live)["data"]["stations"]]


router = APIRouter(prefix="/api/veturilo", tags=["Veturilo (Nextbike GBFS)"])


@router.get("/stations")
def api_stations():
    """Veturilo stations: id, name, number, location, capacity (saved file)."""
    return stations()


@router.get("/stations/{station_id}")
def api_station(station_id: str):
    """One station with its live status."""
    info = next((s for s in stations() if s["station_id"] == station_id), None)
    if not info:
        raise HTTPException(404, "unknown station_id")
    st = next((s for s in status() if s["station_id"] == station_id), None)
    return {**info, "status": st}


@router.get("/status")
def api_status():
    """Live bikes / docks per station (30 s cache)."""
    return status()


@router.get("/free-bikes")
def api_free_bikes():
    """Live list of bikes (at stations and parked outside them)."""
    return _get("free_bike_status", True)["data"]["bikes"]


@router.get("/vehicle-types")
def api_vehicle_types():
    """Bike types (classic, e-bike ...)."""
    return _get("vehicle_types", False)["data"]["vehicle_types"]
