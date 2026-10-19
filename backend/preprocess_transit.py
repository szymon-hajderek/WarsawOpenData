"""Timetable for the router's RAPTOR (POST /plan): every GTFS trip as a list of calls at StationLocations indexes.

Usage (from backend/): uv run python preprocess_transit.py
Output: data/derived/street/timetable.bin (git-ignored). Format: algorithms/router/README.md ("Timetable file").

The router groups the trips into route patterns itself when it loads the file; this file only flattens the GTFS
caches of mkuran:
- a stop_times stop -> mkuran.canonical() -> its index in stations.json (rows at stops outside the overlay dropped);
- consecutive calls at one location collapse into one (arrival of the first, departure of the last);
- frequency templates (metro) are expanded into runs that keep the template's trip id (times shifted);
- services are lists of YYYYMMDD dates.
Boarding restrictions (pickup_type / drop_off_type) are not kept: RAPTOR may board and alight at every call.
"""
import sys
import time

import numpy as np

import stations
from config import DERIVED, REPO, atomic_write

sys.path.insert(0, str(REPO / "algorithms"))
import timetable_file  # noqa: E402

OUT = DERIVED / "street" / "timetable.bin"


def _collapse(loc: np.ndarray, arr: np.ndarray, dep: np.ndarray):
    """Merge consecutive calls at the same location: arrival of the first, departure of the last."""
    if len(loc) == 0:
        return loc, arr, dep
    start = np.r_[True, loc[1:] != loc[:-1]]
    first = np.flatnonzero(start)
    last = np.r_[first[1:] - 1, len(loc) - 1]
    return loc[first], arr[first], dep[last]


def build() -> dict:
    """mkuran caches + stations.json -> timetable.bin. Returns counts."""
    from sources import mkuran

    t0 = time.time()
    doc = stations.load()
    locs = doc["locations"]
    index = {l["id"]: i for i, l in enumerate(locs)}
    stop_loc = np.array([index.get(mkuran.canonical(sid), -1) for sid in mkuran._stop_ids()], dtype=np.int64)

    rts = mkuran.routes()
    route_ids = sorted(rts)
    route_index = {r: i for i, r in enumerate(route_ids)}
    routes = [(r, rts[r]["short_name"], "bus" if rts[r]["mode"] == "trolleybus" else rts[r]["mode"])
              for r in route_ids]
    svc = mkuran.services()
    service_ids = sorted(svc)
    service_index = {s: i for i, s in enumerate(service_ids)}

    st = mkuran.stop_times()
    trips = mkuran.trips()
    freq = mkuran.frequencies()
    bounds = mkuran._trip_bounds()
    loc_all = stop_loc[st["stop"]]
    out = {"trip_route": [], "trip_service": [], "trip_ids": [], "headsigns": [], "trip_offset": [0],
           "call_loc": [], "call_arr": [], "call_dep": []}
    dropped = {"outside": 0, "short": 0, "backwards": 0}  # outside = no call in the area (PKP)
    for ti, trip in enumerate(trips):
        tid, rid, sid = trip[0], trip[1], trip[2]
        a, b = (int(x) for x in bounds[ti])
        if a < 0 or sid not in service_index or rid not in route_index:
            dropped["outside"] += 1
            continue
        keep = loc_all[a:b] >= 0
        loc, arr, dep = _collapse(loc_all[a:b][keep], st["arr"][a:b][keep].astype(np.int64),
                                  st["dep"][a:b][keep].astype(np.int64))
        if len(loc) < 2:
            dropped["short"] += 1
            continue
        times = np.column_stack((arr, dep)).ravel()
        if np.any(np.diff(times) < 0):
            dropped["backwards"] += 1
            continue
        offsets = [0]
        if ti in freq:  # frequency template: one run per headway, like mkuran.departures()
            base = int(st["dep"][a])
            offsets = [s - base + k * hw for s, e, hw in freq[ti] for k in range(max(1, (e - s) // hw))]
        for off in offsets:
            out["trip_route"].append(route_index[rid])
            out["trip_service"].append(service_index[sid])
            out["trip_ids"].append(tid)
            out["headsigns"].append(trip[4] if len(trip) > 4 else "")
            out["call_loc"].append(loc)
            out["call_arr"].append(arr + off)
            out["call_dep"].append(dep + off)
            out["trip_offset"].append(out["trip_offset"][-1] + len(loc))
    for k in ("call_loc", "call_arr", "call_dep"):
        out[k] = np.concatenate(out[k]) if out[k] else np.zeros(0, dtype=np.int64)
    with atomic_write(OUT) as f:
        timetable_file.write(f, doc["hash"], len(locs), routes, [sorted(svc[s]) for s in service_ids], **out)
    return {"trips": len(out["trip_ids"]), "calls": int(len(out["call_loc"])), "routes": len(routes),
            "services": len(service_ids), "dropped": dropped, "seconds": round(time.time() - t0, 1),
            "file_mb": round(OUT.stat().st_size / 1e6, 1)}


def stale() -> bool:
    """The file is missing, older than the GTFS cache or the overlay, or written for another overlay."""
    sources = [DERIVED / "gtfs_stop_times.npz", DERIVED / "gtfs_trips.json", stations.FILE]
    newest = max((f.stat().st_mtime for f in sources if f.exists()), default=0)
    if not OUT.exists() or OUT.stat().st_mtime < newest:
        return True
    return timetable_file.header_hash(OUT) != stations.load()["hash"]


if __name__ == "__main__":
    print(build())
