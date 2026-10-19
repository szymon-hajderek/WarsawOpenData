"""Which vehicle is the user on, and how late is it? Polls live bus and tram positions every 3 s.

Detection: keeps the last 3 positions per vehicle and ranks them by MSE against the user's last 1-3
positions (algorithms/nearest_buses.py). Direction comes from the GTFS trip with the same line and brigade.

Delay: keeps a longer buffer per vehicle (longest scheduled stop-to-stop time of its trip + 60 s) with a
midpoint between feed points, and estimates the delay at the previous stop (algorithms/bus_delay.py).
"""
import logging
import os
import sys
import threading
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import REPO
from sim import clock, scenario

sys.path.insert(0, str(REPO / "algorithms"))
from bus_delay import WINDOW_S, add_point, estimate  # noqa: E402
from route_delays import leg_vehicles, trip_ids_from_option  # noqa: E402
from nearest_buses import rank_buses  # noqa: E402

# When LIVE_BUSES_URL is set, only that feed is polled over HTTP (mode taken from type=).
# Otherwise the bus and the tram feeds are read directly from the City Hall API (fetch_vehicles, needs PORTAL_KEY).
_CUSTOM = os.getenv("LIVE_BUSES_URL")
STALE_S = 300  # a vehicle that has not reported for this long is forgotten
STARTUP_DELAY_S = 2  # LIVE_BUSES_URL may point at our own HTTP server: wait until uvicorn accepts connections
POLL_S = 3  # the feed changes about every 10 s; 3 s catches a new position soon after it appears
HISTORY = 3  # positions kept per vehicle
CANDIDATES = 4  # the popup shows the most likely vehicle + 3 others
DELAY_RADIUS_M = float(os.getenv("DELAY_RADIUS_M", "80"))  # a vehicle "passed" a stop when this close (search: radius-search.html)
BUFFER_MARGIN_S = 60  # added to the longest scheduled stop-to-stop time of the trip
BUFFER_DEFAULT_S = 600  # buffer length when no trip runs for the vehicle

log = logging.getLogger(__name__)
_lock = threading.Lock()
_history: dict[str, list[dict]] = {}  # vehicle id -> last positions {"lat", "lon", "t"}, oldest first
_info: dict[str, dict] = {}  # vehicle id -> line, brigade, mode, direction
_buffers: dict[str, list[dict]] = {}  # vehicle id -> positions + midpoints for the delay, oldest first
_broken: set[str] = set()  # vehicles whose next point follows a failed poll (no midpoint then)
_last_proj: dict[str, dict] = {}  # vehicle id -> {"trip_id", "dist"} of the last delay estimate (loops)
_updated_at: float | None = None


def _feeds() -> list[tuple[str, str]]:
    if _CUSTOM:
        mode = "tram" if "type=tram" in _CUSTOM else "bus"
        return [(mode, _CUSTOM)]
    base = "http://localhost:8000/api/live/vehicles"
    return [("bus", f"{base}?type=bus"), ("tram", f"{base}?type=tram")]


def _epoch(local_time: str) -> float:
    """Feed time is Warsaw local time, whatever the server's time zone."""
    return clock.warsaw_epoch(datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S"))


def _direction(line: str, brigade: str, local_time: str) -> str:
    try:
        from sources import mkuran
        clock = datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S")
        sec = clock.hour * 3600 + clock.minute * 60 + clock.second
        return mkuran.headsign_for(line, brigade, clock.strftime("%Y%m%d"), sec)
    except Exception as exc:
        log.warning("headsign lookup failed: %s", exc)
        return ""


def _keep_s(line: str, brigade: str, local_time: str) -> float:
    try:
        from sources import mkuran
        seg = mkuran.max_segment_for(line, brigade, datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        log.warning("trip lookup failed: %s", exc)
        seg = None
    return BUFFER_DEFAULT_S if seg is None else seg + BUFFER_MARGIN_S


def _store(mode: str, rows: list[dict]) -> None:
    with _lock:
        for v in rows:
            vid = f"{mode}-{v['vehicle']}"
            point = {"lat": v["lat"], "lon": v["lon"], "t": _epoch(v["time"])}
            track = _history.setdefault(vid, [])
            if not track or track[-1]["t"] != point["t"]:
                track.append(point)
                del track[:-HISTORY]
                add_point(_buffers.setdefault(vid, []), point, vid in _broken,
                          _keep_s(v["line"], v["brigade"], v["time"]))
                _broken.discard(vid)
            _info[vid] = {"vehicle": v["vehicle"], "line": v["line"], "brigade": v["brigade"],
                          "mode": mode, "direction": _direction(v["line"], v["brigade"], v["time"])}


def _forget_stale() -> None:
    """Drop vehicles that left the feed, so they are not ranked and the dicts do not grow."""
    cutoff = clock.now() - STALE_S
    with _lock:
        for vid in [vid for vid, track in _history.items() if not track or track[-1]["t"] < cutoff]:
            del _history[vid]
            for d in (_info, _buffers, _last_proj):
                d.pop(vid, None)
            _broken.discard(vid)


def _mark_broken(mode: str) -> None:
    """A poll of this feed failed: the next point of each of its vehicles gets no midpoint."""
    with _lock:
        _broken.update(vid for vid, i in _info.items() if i["mode"] == mode)


def poll_once() -> bool:
    global _updated_at
    batches: list[tuple[str, list]] = []
    if _CUSTOM:
        for mode, url in _feeds():
            try:
                response = httpx.get(url, timeout=30)
                response.raise_for_status()
                rows = response.json()
            except Exception as exc:
                log.warning("live %s poll failed: %s", mode, exc)
                _mark_broken(mode)
                continue
            if isinstance(rows, list):
                batches.append((mode, rows))
    else:
        from sources.um_warszawa import fetch_vehicles
        for mode in ("bus", "tram"):
            try:
                batches.append((mode, fetch_vehicles(mode)))
            except Exception as exc:
                log.warning("live %s poll failed: %s", mode, exc)
                _mark_broken(mode)
    for mode, rows in batches:
        _store(mode, rows)
    if batches:
        _forget_stale()
        _updated_at = clock.now()
    return bool(batches)


def _loop() -> None:
    time.sleep(STARTUP_DELAY_S)
    while True:
        try:
            poll_once()
        except Exception as e:  # keep polling: the feed or the network can fail for a while
            log.warning("live bus poll failed: %s", e)
        time.sleep(POLL_S)


def reset() -> None:
    """Forget all vehicles (a new simulation scenario starts)."""
    global _updated_at
    with _lock:
        for d in (_history, _info, _buffers, _last_proj):
            d.clear()
        _broken.clear()
        _updated_at = None


def start_poller() -> None:
    from config import PORTAL_KEY
    if scenario.current():
        log.warning("live vehicle poller off: simulation mode, the sim clock polls on each step")
        return
    if not _CUSTOM and not PORTAL_KEY:
        log.warning("live vehicle poller off: PORTAL_KEY is not set")
        return
    threading.Thread(target=_loop, daemon=True, name="bus-poller").start()


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/live", tags=["bus detection"])


class UserPoint(BaseModel):
    lat: float
    lon: float
    time_ms: float


class NearestRequest(BaseModel):
    points: list[UserPoint]


def _need_data() -> None:
    if _updated_at is None:  # the poller has not got data yet
        try:
            poll_once()
        except Exception:
            log.exception("on-demand live poll failed")
        if _updated_at is None:
            raise HTTPException(503, "no live vehicle data yet, try again in a few seconds")


@router.post("/nearest-buses")
def api_nearest_buses(req: NearestRequest):
    """The buses closest to the user's last 1-3 positions (lowest MSE first) + all live lines."""
    if not req.points:
        raise HTTPException(400, "send at least one point")
    _need_data()
    user = [{"lat": p.lat, "lon": p.lon, "t": p.time_ms / 1000} for p in req.points[-HISTORY:]]
    with _lock:
        ranked = rank_buses(user, _history, CANDIDATES)
        candidates = [{"id": r["id"], **_info[r["id"]], "rmse_m": round(r["rmse_m"], 1)} for r in ranked]
        lines = sorted({i["line"] for i in _info.values()}, key=lambda s: (len(s), s))
    return {"candidates": candidates, "lines": lines, "updated_at": _updated_at}

def _clock(epoch: float | None) -> str | None:
    return None if epoch is None else clock.warsaw_time(epoch).strftime("%H:%M:%S")


@router.get("/delay")
def api_delay(vehicle: str = Query(..., description="vehicle id as in nearest-buses, e.g. bus-5914")):
    """Estimated delay of one vehicle at its previous stop, shown as the expected delay at the next stop."""
    _need_data()
    answer = _delay_for(vehicle)
    if answer is None:
        raise HTTPException(404, "unknown vehicle")
    return answer


def _delay_for(vehicle: str) -> dict | None:
    """The /delay answer for one live vehicle, None when the vehicle is unknown."""
    with _lock:
        info = _info.get(vehicle)
        buffer = list(_buffers.get(vehicle, ()))
        prev = _last_proj.get(vehicle)
    if info is None:
        return None
    from sources import mkuran
    when = clock.warsaw_time(buffer[-1]["t"]) if buffer else clock.warsaw_now()
    r = estimate(buffer, mkuran.brigade_trips(info["line"], info["brigade"], when, WINDOW_S), DELAY_RADIUS_M, prev)
    trip = r["trip"]
    if trip is not None:
        with _lock:
            _last_proj[vehicle] = {"trip_id": trip["trip_id"], "dist": r["dist"]}
    prev_stop = next_stop = None
    if r["prev_index"] is not None:
        k1, k = trip["stops"][r["prev_index"]], trip["stops"][r["prev_index"] + 1]
        delay = r["delay_s"]
        prev_stop = {"id": k1["id"], "name": k1["name"], "scheduled": _clock(k1["sched"]),
                     "passedAt": _clock(r["passed_at"])}
        next_stop = {"id": k["id"], "name": k["name"], "scheduled": _clock(k["sched"]),
                     "expected": None if delay is None else _clock(k["sched"] + delay)}
    return {"vehicleId": vehicle, "vehicle": info["vehicle"], "line": info["line"], "brigade": info["brigade"],
            "mode": info["mode"], "tripId": trip["trip_id"] if trip else None,
            "headsign": trip["headsign"] if trip else None, "available": r["available"], "reason": r["reason"],
            "delaySec": r["delay_s"], "prevStop": prev_stop, "nextStop": next_stop,
            "radiusM": DELAY_RADIUS_M, "updatedAt": _updated_at}


class RouteDelayOption(BaseModel):
    id: str
    lines: list[str]


class RouteDelaysRequest(BaseModel):
    options: list[RouteDelayOption] = Field(max_length=20)


def _gtfs_trip(trip_id: str) -> dict | None:
    """Line, brigade and mode of a GTFS trip, None when GTFS does not know it."""
    from sources import mkuran
    ti = mkuran._trip_ids().get(trip_id)
    if ti is None:
        return None
    trip = mkuran.trips()[ti]
    route = mkuran.routes().get(trip[1], {})
    return {"line": route.get("short_name", ""), "brigade": str(trip[3]), "mode": route.get("mode", "")}


@router.post("/route-delays")
def api_route_delays(req: RouteDelaysRequest):
    """Live delay of the buses and trams in suggested routes, before the user boards them (data/API.md)."""
    _need_data()
    with _lock:
        vehicles = {(i["line"], str(i["brigade"])): vid for vid, i in _info.items()}
    out = {}
    for option in req.options:
        trip_ids = trip_ids_from_option(option.id)
        trips = {t: g for t in trip_ids if (g := _gtfs_trip(t)) is not None}
        rows = []
        for row in leg_vehicles(trip_ids, option.lines, trips, vehicles):
            item = {"transitIndex": row["transitIndex"], "line": row["line"], "vehicleId": row["vehicle_id"],
                    "available": False, "delaySec": None, "sameTrip": False, "reason": row["reason"]}
            answer = _delay_for(row["vehicle_id"]) if row["vehicle_id"] else None
            if answer is not None:
                item.update(available=answer["available"], delaySec=answer["delaySec"], reason=answer["reason"],
                            sameTrip=answer["tripId"] == row["trip_id"])
            rows.append(item)
        out[option.id] = rows
    return out
