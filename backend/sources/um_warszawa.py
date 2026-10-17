"""Warsaw City Hall APIs: live ZTM vehicle positions (dane.um.warszawa.pl) and per-stop lines /
timetables + official route variants (api.um.warszawa.pl).

These are NOT a second stop list. Stops come from GTFS (mkuran). IDs map 1:1:
  GTFS "ztm:700901"  <->  busstopId="7009" (nr_zespolu), busstopNr="01" (nr_przystanku)
  GTFS route_short_name "131"  <->  live "Lines" / timetable "line"
  GTFS trips.block_short_name  <->  live "Brigade" / timetable "brygada"

Keys from .env: PORTAL_KEY (dane.um, header Authorization), WAW_API_KEY (api.um, query apikey).
"""
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query

from config import LIVE_DIR, PORTAL_KEY, WAW_API_KEY, TTLCache, load_json, save_json

PORTAL = "https://dane.um.warszawa.pl/api/action"
API = "https://api.um.warszawa.pl/api/action"
LINES_AT_STOP_ID = "88cd555f-6f31-43ca-9de4-66c479ad5942"
TIMES_ID = "e923fa0e-d96c-43f9-ae6e-60518c9f3238"
VEHICLE_TYPES = {"bus": 1, "tram": 2}

_cache = TTLCache(30)


# ---------------------------------------------------------------- id mapping

def split_stop_id(stop_id: str) -> tuple[str, str]:
    """'ztm:700901' -> ('7009', '01')."""
    raw = stop_id.removeprefix("ztm:")
    if not (raw.isdigit() and len(raw) == 6):
        raise ValueError("only ZTM bus / tram posts have a City Hall id (e.g. ztm:700901)")
    return raw[:4], raw[4:]


def join_stop_id(zespol: str, slupek: str) -> str:
    return f"ztm:{zespol}{slupek}"


# ---------------------------------------------------------------- fetchers

def fetch_vehicles(kind: str) -> list[dict]:
    r = httpx.post(f"{PORTAL}/get_ztm_lokalizacja_pojazdow", json={"type": VEHICLE_TYPES[kind]},
                   headers={"Authorization": PORTAL_KEY}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"unexpected answer: {str(data)[:200]}")
    return [{"line": v["Lines"], "brigade": v["Brigade"], "lat": v["Lat"], "lon": v["Lon"],
             "time": v["Time"], "vehicle": v["VehicleNumber"], "mode": kind,
             "route_id": f"ztm:{v['Lines']}"} for v in data]


def fresh(vehicles: list[dict], max_age_s: int = 300, now: datetime | None = None) -> list[dict]:
    """The feed also returns vehicles that stopped reporting long ago (even years). Drop them."""
    now = now or datetime.now()
    return [v for v in vehicles
            if (now - datetime.strptime(v["time"], "%Y-%m-%d %H:%M:%S")).total_seconds() <= max_age_s]


def _dbtimetable(params: dict):
    r = httpx.get(f"{API}/dbtimetable_get/", params={**params, "apikey": WAW_API_KEY}, timeout=30)
    r.raise_for_status()
    result = r.json().get("result")
    if isinstance(result, str):
        raise RuntimeError(result)
    return result or []


def _kv(row) -> dict:
    return {x["key"]: x["value"] for x in row}


def fetch_lines_at_stop(stop_id: str) -> list[str]:
    zespol, slupek = split_stop_id(stop_id)
    rows = _dbtimetable({"id": LINES_AT_STOP_ID, "busstopId": zespol, "busstopNr": slupek})
    return [_kv(r["values"])["linia"] for r in rows]


def fetch_times(stop_id: str, line: str) -> list[dict]:
    zespol, slupek = split_stop_id(stop_id)
    rows = _dbtimetable({"id": TIMES_ID, "busstopId": zespol, "busstopNr": slupek, "line": line})
    return [{"time": d["czas"], "brigade": d["brygada"], "direction": d["kierunek"], "variant": d["trasa"]}
            for d in map(_kv, rows)]


def fetch_route_variants() -> dict:
    """Official route variants: line -> variant -> order -> {nr_zespolu, nr_przystanku, odleglosc ...}."""
    r = httpx.get(f"{API}/public_transport_routes/", params={"apikey": WAW_API_KEY}, timeout=120)
    r.raise_for_status()
    return r.json()["result"]


# ---------------------------------------------------------------- download (snapshot)

def download() -> list[str]:
    """Save one snapshot of each live endpoint as a sample in data/live/."""
    files = []
    for kind in VEHICLE_TYPES:
        save_json(LIVE_DIR / f"ztm_vehicles_{kind}.json", fetch_vehicles(kind))
        files.append(f"ztm_vehicles_{kind}.json")
    save_json(LIVE_DIR / "ztm_route_variants.json", fetch_route_variants())
    files.append("ztm_route_variants.json")
    sample = "ztm:700901"
    lines = fetch_lines_at_stop(sample)
    save_json(LIVE_DIR / "ztm_stop_700901_lines.json", lines)
    save_json(LIVE_DIR / f"ztm_stop_700901_line_{lines[0]}_times.json", fetch_times(sample, lines[0]))
    files += ["ztm_stop_700901_lines.json", f"ztm_stop_700901_line_{lines[0]}_times.json"]
    return files


def route_variants_snapshot() -> dict:
    return load_json(LIVE_DIR / "ztm_route_variants.json")


def vehicles_snapshot() -> list[dict]:
    out = []
    for kind in VEHICLE_TYPES:
        p = LIVE_DIR / f"ztm_vehicles_{kind}.json"
        if p.exists():
            out += load_json(p)
    return out


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api", tags=["um.warszawa.pl (live)"])


@router.get("/live/vehicles")
def api_vehicles(type: str = Query("bus", description="bus or tram"), line: str | None = None,
                 max_age_s: int = Query(300, description="drop positions older than this")):
    """Live ZTM bus / tram positions (30 s cache). route_id matches /api/gtfs/routes."""
    if type not in VEHICLE_TYPES:
        raise HTTPException(400, "type must be bus or tram")
    data = fresh(_cache.get(("veh", type), lambda: fetch_vehicles(type)), max_age_s)
    return [v for v in data if not line or v["line"] == line]


@router.get("/ztm/stops/{stop_id}/lines")
def api_lines(stop_id: str):
    """Lines that stop at a ZTM post (City Hall timetable API)."""
    try:
        return _cache.get(("lines", stop_id), lambda: fetch_lines_at_stop(stop_id))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/ztm/stops/{stop_id}/lines/{line}/times")
def api_times(stop_id: str, line: str):
    """Today's planned times of one line at one ZTM post (City Hall timetable API)."""
    try:
        return _cache.get(("times", stop_id, line), lambda: fetch_times(stop_id, line))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/ztm/routes/{line}")
def api_route_variants(line: str):
    """Official route variants of a line with GTFS stop ids and distances (snapshot file)."""
    data = route_variants_snapshot().get(line)
    if data is None:
        raise HTTPException(404, "unknown line")
    return {variant: [{"order": int(k), "stop_id": join_stop_id(v["nr_zespolu"], v["nr_przystanku"]),
                       "distance_m": v["odleglosc"], "type": v["typ"]}
                      for k, v in sorted(stops.items(), key=lambda kv: int(kv[0]))]
            for variant, stops in data.items()}
