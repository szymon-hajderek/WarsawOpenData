"""Which vehicle is the user on? Polls live bus and tram positions every 3 s, keeps a short history
per vehicle and ranks them by MSE against the user's last 1-3 positions (algorithms/nearest_buses.py).

Direction comes from the GTFS trip with the same line and brigade (trip_headsign).
"""
import logging
import os
import sys
import threading
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import REPO

sys.path.insert(0, str(REPO / "algorithms"))
from nearest_buses import rank_buses  # noqa: E402

# When LIVE_BUSES_URL is set, only that feed is polled (mode taken from type=).
# Otherwise both the bus and the tram feeds of this server are polled.
_CUSTOM = os.getenv("LIVE_BUSES_URL")
STALE_S = 300  # a vehicle that has not reported for this long is forgotten
STARTUP_DELAY_S = 2  # the poller reads our own HTTP server: wait until uvicorn accepts connections
POLL_S = 3  # the feed changes about every 10 s; 3 s catches a new position soon after it appears
HISTORY = 3  # positions kept per vehicle
CANDIDATES = 4  # the popup shows the most likely vehicle + 3 others

log = logging.getLogger(__name__)
_lock = threading.Lock()
_history: dict[str, list[dict]] = {}  # vehicle id -> last positions {"lat", "lon", "t"}, oldest first
_info: dict[str, dict] = {}  # vehicle id -> line, brigade, mode, direction
_updated_at: float | None = None


def _feeds() -> list[tuple[str, str]]:
    if _CUSTOM:
        mode = "tram" if "type=tram" in _CUSTOM else "bus"
        return [(mode, _CUSTOM)]
    base = "http://localhost:8000/api/live/vehicles"
    return [("bus", f"{base}?type=bus"), ("tram", f"{base}?type=tram")]


def _epoch(local_time: str) -> float:
    """Feed time is Warsaw local time; the server is assumed to run in the same time zone."""
    return datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S").timestamp()


def _direction(line: str, brigade: str, local_time: str) -> str:
    try:
        from sources import mkuran
        clock = datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S")
        sec = clock.hour * 3600 + clock.minute * 60 + clock.second
        return mkuran.headsign_for(line, brigade, clock.strftime("%Y%m%d"), sec)
    except Exception as exc:
        log.warning("headsign lookup failed: %s", exc)
        return ""


def _forget_stale() -> None:
    """Drop vehicles that left the feed, so they are not ranked and the dicts do not grow."""
    cutoff = time.time() - STALE_S
    with _lock:
        for vid in [vid for vid, track in _history.items() if not track or track[-1]["t"] < cutoff]:
            del _history[vid]
            _info.pop(vid, None)


def poll_once() -> None:
    global _updated_at
    got = False
    for mode, url in _feeds():
        try:
            r = httpx.get(url, timeout=30)
            r.raise_for_status()
            rows = r.json()
        except Exception as exc:
            log.warning("live %s poll failed: %s", mode, exc)
            continue
        got = True
        with _lock:
            for v in rows:
                vid = f"{mode}-{v['vehicle']}"
                point = {"lat": v["lat"], "lon": v["lon"], "t": _epoch(v["time"])}
                track = _history.setdefault(vid, [])
                if not track or track[-1]["t"] != point["t"]:
                    track.append(point)
                    del track[:-HISTORY]
                _info[vid] = {"vehicle": v["vehicle"], "line": v["line"], "brigade": v["brigade"],
                              "mode": mode, "direction": _direction(v["line"], v["brigade"], v["time"])}
    if got:
        _forget_stale()
        _updated_at = time.time()


def _loop() -> None:
    time.sleep(STARTUP_DELAY_S)
    while True:
        try:
            poll_once()
        except Exception as e:  # keep polling: the feed or the network can fail for a while
            log.warning("live bus poll failed: %s", e)
        time.sleep(POLL_S)


def start_poller() -> None:
    threading.Thread(target=_loop, daemon=True, name="bus-poller").start()


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/live", tags=["bus detection"])


class UserPoint(BaseModel):
    lat: float
    lon: float
    time_ms: float


class NearestRequest(BaseModel):
    points: list[UserPoint]


@router.post("/nearest-buses")
def api_nearest_buses(req: NearestRequest):
    """The buses closest to the user's last 1-3 positions (lowest MSE first) + all live lines."""
    if not req.points:
        raise HTTPException(400, "send at least one point")
    if _updated_at is None:  # the poller has not got data yet
        try:
            poll_once()
        except Exception:
            log.exception("on-demand live poll failed")
        if _updated_at is None:
            raise HTTPException(503, "no live vehicle data yet, try again in a few seconds")
    user = [{"lat": p.lat, "lon": p.lon, "t": p.time_ms / 1000} for p in req.points[-HISTORY:]]
    with _lock:
        ranked = rank_buses(user, _history, CANDIDATES)
        candidates = [{"id": r["id"], **_info[r["id"]], "rmse_m": round(r["rmse_m"], 1)} for r in ranked]
        lines = sorted({i["line"] for i in _info.values()}, key=lambda s: (len(s), s))
    return {"candidates": candidates, "lines": lines, "updated_at": _updated_at}
