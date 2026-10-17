"""Synthetic ZTM bus and tram positions from the GTFS timetable and shapes.

Each running trip gives one vehicle. Between two stops the vehicle moves along the shape at a constant
speed; at a stop it waits from `arr` to `dep`. A delay moves a vehicle back in its timetable. Rows have
the same form as `um_warszawa.fetch_vehicles`, plus `trip` (trip index) and `dist` (metres along the
shape) for the test code. The feed reports every `FEED_EVERY_S` seconds, so positions are taken at that
moment, like the City Hall feed.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from sim import clock

FEED_EVERY_S = 10
MODES = ("bus", "tram")


@lru_cache
def _trip_table() -> dict:
    """Per-trip arrays: first departure, last arrival, line, brigade, mode, service id."""
    from sources import mkuran

    trips = mkuran.trips()
    routes = mkuran.routes()
    st = mkuran.stop_times()
    bounds = mkuran._trip_bounds()
    n = len(trips)
    first = np.full(n, -1, dtype=np.int64)
    last = np.full(n, -1, dtype=np.int64)
    ok = bounds[:, 0] >= 0
    first[ok] = st["dep"][bounds[ok, 0]]
    last[ok] = st["arr"][bounds[ok, 1] - 1]
    line = np.array([routes.get(t[1], {}).get("short_name", "") for t in trips], dtype=object)
    mode = np.array([routes.get(t[1], {}).get("mode", "") if t[1].startswith("ztm:") else "" for t in trips],
                    dtype=object)
    brigade = np.array([t[3] for t in trips], dtype=object)
    service = np.array([t[2] for t in trips], dtype=object)
    return {"first": first, "last": last, "line": line, "mode": mode, "brigade": brigade, "service": service}


@lru_cache(maxsize=8)
def _running_on(date_str: str) -> np.ndarray:
    """Trip indices of ZTM buses and trams that run on a service date."""
    from sources import mkuran

    svc = mkuran.services()
    table = _trip_table()
    on = {sid for sid, dates in svc.items() if date_str in dates}
    mask = np.array([s in on for s in table["service"]]) & np.isin(table["mode"], MODES) & (table["first"] >= 0)
    return np.flatnonzero(mask)


def _position(ti: int, sec: float) -> tuple[float, float, float] | None:
    """(lat, lon, metres along the shape) of trip `ti` at `sec` seconds after its service midnight."""
    from sources import mkuran

    static = mkuran._trip_static(int(ti))
    if static is None:
        return None
    stops, (metres, lat, lon) = static
    if sec < stops[0]["dep"] or sec > stops[-1]["arr"]:
        return None
    dist = stops[-1]["dist"]
    for a, b in zip(stops, stops[1:]):
        if sec <= a["dep"]:
            dist = a["dist"]
            break
        if sec < b["arr"]:
            span = max(1, b["arr"] - a["dep"])
            dist = a["dist"] + (b["dist"] - a["dist"]) * (sec - a["dep"]) / span
            break
    return float(np.interp(dist, metres, lat)), float(np.interp(dist, metres, lon)), float(dist)


_last: tuple = (None, [])  # (key, rows) of the last call: one feed step is read many times


def vehicles(epoch: float, delays: dict[tuple[str, str | None], float] | None = None) -> list[dict]:
    """All running ZTM buses and trams at `epoch` (floored to the feed step).

    `delays` maps (line, brigade) or (line, None) for the whole line to seconds late.
    """
    global _last
    at = epoch - epoch % FEED_EVERY_S
    key = (at, tuple(sorted((delays or {}).items(), key=str)))
    if _last[0] != key:
        _last = (key, _compute(at, delays or {}))
    return _last[1]


def _compute(at: float, delays: dict) -> list[dict]:
    from sources import mkuran

    wall = clock.warsaw_time(at)
    table = _trip_table()
    # a delayed vehicle can still be on a trip whose timetable has already ended
    margin = max(delays.values(), default=0.0) + 60
    rows: dict[tuple[str, str], dict] = {}
    for date_str, _, sec in mkuran._service_days(wall):
        idx = _running_on(date_str)
        near = idx[(table["first"][idx] <= sec) & (table["last"][idx] >= sec - margin)]
        for ti in near:
            line, brigade = table["line"][ti], table["brigade"][ti]
            if (line, brigade) in rows:
                continue
            late = delays.get((line, brigade), delays.get((line, None), 0.0))
            pos = _position(int(ti), sec - late)
            if pos is None:
                continue
            rows[(line, brigade)] = {
                "line": line, "brigade": brigade, "lat": round(pos[0], 6), "lon": round(pos[1], 6),
                "time": wall.strftime("%Y-%m-%d %H:%M:%S"), "vehicle": f"S{line}-{brigade}",
                "mode": table["mode"][ti], "route_id": f"ztm:{line}", "trip": int(ti), "dist": pos[2],
            }
    return list(rows.values())


def trip_stops(ti: int) -> list[dict]:
    """Stops of a trip with `dist` (metres along the shape), for direction checks in tests."""
    from sources import mkuran

    static = mkuran._trip_static(int(ti))
    return [] if static is None else static[0]
