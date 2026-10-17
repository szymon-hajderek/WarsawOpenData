"""mkuran.pl GTFS feeds: stop locations and timetables for ZTM (bus, tram, metro, SKM), WKD and
other trains (KM, PKP Intercity, PolRegio ...).

Dedup rules (GTFS is the base for all stops):
- ZTM incl. metro + SKM comes from warsaw.zip.
- WKD comes from wkd.zip.
- polish_trains.zip: SKM is dropped (already in warsaw.zip), stops outside the ZTM area are dropped.
- A train station from polish_trains / WKD is merged into a ZTM *rail* stop when the names match and
  the distance is < 150 m. Train stations are never merged with bus / tram / metro stops.

Global stop ids are prefixed with the feed: "ztm:700901", "wkd:brzoz", "pkp:33605_RAIL_1_5".
ZTM stop_id = stop group (zespół, 4 digits) + post (słupek, 2 digits): "7009" + "01" -> "700901".
"""
import csv
import io
import sys
import threading
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import lru_cache

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Query

from sim import clock
from config import (BBOX, DERIVED, GTFS_DIR, REPO, atomic_write, haversine_m, in_bbox, load_json, save_json,
                    save_npz)

sys.path.insert(0, str(REPO / "algorithms"))
from shape_units import shape_meters  # noqa: E402
from station_map import parse_platform_code  # noqa: E402

FEEDS = {
    "ztm": ("warsaw.zip", "https://mkuran.pl/gtfs/warsaw.zip"),
    "wkd": ("wkd.zip", "https://mkuran.pl/gtfs/wkd.zip"),
    "pkp": ("polish_trains.zip", "https://mkuran.pl/gtfs/polish_trains.zip"),
}
# SKM is in both feeds. polish_trains has it per platform + track, warsaw.zip as one stop per station,
# so the rail routes of warsaw.zip (route_type 2 = SKM) are dropped and SKM comes from polish_trains.
DROP_PKP_AGENCIES: set[str] = set()
DROP_ZTM_ROUTE_TYPES = {2}
MERGE_RADIUS_M = 150
ROUTE_TYPES = {0: "tram", 1: "metro", 2: "rail", 3: "bus", 11: "trolleybus"}


# ---------------------------------------------------------------- download

def download() -> list[str]:
    GTFS_DIR.mkdir(parents=True, exist_ok=True)
    done = []
    with httpx.Client(follow_redirects=True, timeout=300) as client:
        for name, url in FEEDS.values():
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with atomic_write(GTFS_DIR / name) as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            done.append(name)
    return done


# ---------------------------------------------------------------- raw readers

def _rows(feed: str, table: str):
    path = GTFS_DIR / FEEDS[feed][0]
    with zipfile.ZipFile(path) as z:
        if table not in z.namelist():
            return
        with z.open(table) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


def _sec(t: str) -> int:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _shape_dist(value) -> int:
    return shape_meters(value)


def _norm_name(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


@lru_cache
def routes() -> dict:
    """Global route id -> route info. SKM of warsaw.zip is dropped (it comes from polish_trains)."""
    out = {}
    for feed in FEEDS:
        for r in _rows(feed, "routes.txt"):
            if feed == "pkp" and r["agency_id"] in DROP_PKP_AGENCIES:
                continue
            rt = int(r["route_type"])
            if feed == "ztm" and rt in DROP_ZTM_ROUTE_TYPES:
                continue
            out[f"{feed}:{r['route_id']}"] = {
                "id": f"{feed}:{r['route_id']}",
                "feed": feed,
                "short_name": r["route_short_name"],
                "long_name": r["route_long_name"],
                "agency": r["agency_id"],
                "type": rt,
                "mode": ROUTE_TYPES.get(rt, str(rt)),
                "color": r.get("route_color", ""),
            }
    return out


@lru_cache
def services() -> dict:
    """Global service id -> set of 'YYYYMMDD' dates (calendar.txt + calendar_dates.txt)."""
    out: dict[str, set] = defaultdict(set)
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for feed in FEEDS:
        for c in _rows(feed, "calendar.txt"):
            d = datetime.strptime(c["start_date"], "%Y%m%d").date()
            end = datetime.strptime(c["end_date"], "%Y%m%d").date()
            while d <= end:
                if c[days[d.weekday()]] == "1":
                    out[f"{feed}:{c['service_id']}"].add(d.strftime("%Y%m%d"))
                d += timedelta(days=1)
        for c in _rows(feed, "calendar_dates.txt"):
            key = f"{feed}:{c['service_id']}"
            if c["exception_type"] == "1":
                out[key].add(c["date"])
            else:
                out[key].discard(c["date"])
    return dict(out)


def _raw_stops(feed: str) -> list[dict]:
    out = []
    for s in _rows(feed, "stops.txt"):
        lt = int(s.get("location_type") or 0)
        out.append({
            "id": f"{feed}:{s['stop_id']}",
            "feed": feed,
            "raw_id": s["stop_id"],
            "name": s["stop_name"],
            "code": s.get("stop_code") or s.get("platform_code") or "",
            "lat": float(s["stop_lat"]),
            "lon": float(s["stop_lon"]),
            "location_type": lt,
            "parent": f"{feed}:{s['parent_station']}" if s.get("parent_station") else None,
            "wheelchair": s.get("wheelchair_boarding", ""),
            "zone": s.get("zone_id", ""),
        })
    return out


def _rail_platforms(stops_out: list[dict]) -> list[dict]:
    """PKP platform children ("2 t. 20", "2 t. 22") fold into one platform location pkp:<station>_P2 (new records);
    children without a platform (FALLBACK) fold into their station. Children get `platform`, the location `members`."""
    by_id = {s["id"]: s for s in stops_out}
    groups = defaultdict(list)
    for s in stops_out:
        if s["feed"] == "pkp" and s["location_type"] == 0 and s["parent"] in by_id:
            parsed = parse_platform_code(s["code"])
            groups[(s["parent"], parsed[0] if parsed else None)].append(s)
    new = []
    for (station_id, number), kids in groups.items():
        station = by_id[station_id]
        if number is None:
            target = station  # trips without a platform board at the station itself
        else:
            target = {**station, "id": f"{station_id}_P{number}", "raw_id": f"{station['raw_id']}_P{number}",
                      "code": f"peron {number}", "location_type": 0, "parent": station_id,
                      "lat": sum(k["lat"] for k in kids) / len(kids), "lon": sum(k["lon"] for k in kids) / len(kids),
                      "group": station_id, "same_as": None, "platform": None, "members": []}
            new.append(target)
        target["members"] = [k["id"] for k in kids]
        target["served"] = any(k["served"] for k in kids)
        target["modes"] = sorted({m for k in kids for m in k["modes"]})
        for k in kids:
            k["platform"] = target["id"]
    return new


def _stop_group(stop: dict) -> str:
    """ZTM stop group (zespół) for numeric posts, else the parent station, else the stop itself."""
    if stop["feed"] == "ztm" and stop["raw_id"].isdigit() and len(stop["raw_id"]) == 6:
        return "ztm:" + stop["raw_id"][:4]
    return stop["parent"] or stop["id"]


# ---------------------------------------------------------------- build (cached)

def _build() -> None:
    """Parse all feeds once and write compact caches to data/derived/."""
    DERIVED.mkdir(parents=True, exist_ok=True)
    rts = routes()

    # stops
    all_stops = {}
    for feed in FEEDS:
        for s in _raw_stops(feed):
            if feed == "pkp" and not in_bbox(s["lat"], s["lon"]):
                continue
            all_stops[s["id"]] = s
    stop_index = {sid: i for i, sid in enumerate(all_stops)}

    # trips
    trips = []  # (global trip id, route id, service id)
    trip_index = {}
    for feed in FEEDS:
        for t in _rows(feed, "trips.txt"):
            rid = f"{feed}:{t['route_id']}"
            if rid not in rts:
                continue  # dropped agency
            tid = f"{feed}:{t['trip_id']}"
            trip_index[tid] = len(trips)
            shape = t.get("shape_id") or ""
            trips.append((tid, rid, f"{feed}:{t['service_id']}", t.get("block_short_name", ""),
                          t.get("trip_headsign", ""), t.get("wheelchair_accessible", ""),
                          f"{feed}:{shape}" if shape else ""))

    # stop_times -> arrays. pos = position in the original trip (to know which rows were adjacent).
    trip_col, pos_col, stop_col, arr_col, dep_col, dist_col = [], [], [], [], [], []
    for feed in FEEDS:
        last_trip, pos = None, -1
        for r in _rows(feed, "stop_times.txt"):
            tid = f"{feed}:{r['trip_id']}"
            ti = trip_index.get(tid)
            if ti is None:
                continue
            pos = pos + 1 if tid == last_trip else 0
            last_trip = tid
            si = stop_index.get(f"{feed}:{r['stop_id']}")
            if si is None:
                continue  # outside the area
            trip_col.append(ti)
            pos_col.append(int(r["stop_sequence"]) if feed != "pkp" else pos)
            stop_col.append(si)
            arr_col.append(_sec(r["arrival_time"] or r["departure_time"]))
            dep_col.append(_sec(r["departure_time"] or r["arrival_time"]))
            dist_col.append(_shape_dist(r.get("shape_dist_traveled")))

    st = {
        "trip": np.array(trip_col, dtype=np.int32),
        "pos": np.array(pos_col, dtype=np.int32),
        "stop": np.array(stop_col, dtype=np.int32),
        "arr": np.array(arr_col, dtype=np.int32),
        "dep": np.array(dep_col, dtype=np.int32),
        "shape_dist": np.array(dist_col, dtype=np.int32),
    }
    order = np.lexsort((st["pos"], st["trip"]))
    st = {k: v[order] for k, v in st.items()}

    # frequencies (metro): number of runs per template trip
    runs = np.ones(len(trips), dtype=np.int32)
    freq = defaultdict(list)
    for feed in FEEDS:
        for f in _rows(feed, "frequencies.txt"):
            ti = trip_index.get(f"{feed}:{f['trip_id']}")
            if ti is None:
                continue
            start, end, hw = _sec(f["start_time"]), _sec(f["end_time"]), int(f["headway_secs"])
            freq[ti].append((start, end, hw))
    for ti, windows in freq.items():
        runs[ti] = sum(max(1, (e - s) // hw) for s, e, hw in windows)

    # which stops are served, which route types serve them
    served_types = defaultdict(set)
    trip_route_type = np.array([rts[t[1]]["type"] for t in trips], dtype=np.int16)
    for si, rt in set(zip(st["stop"].tolist(), trip_route_type[st["trip"]].tolist())):
        served_types[si].add(rt)

    # rail-to-rail merge: pkp / wkd stations -> ZTM rail stop (route_type 2)
    ztm_rail = [all_stops[sid] for sid, i in stop_index.items()
                if sid.startswith("ztm:") and 2 in served_types.get(i, ())]
    merged = {}  # stop id -> canonical stop id
    unmatched_near = []
    for s in all_stops.values():
        if s["feed"] == "ztm":
            continue
        is_station = s["location_type"] == 1 or (s["feed"] == "wkd")
        if not is_station:
            continue
        best = None
        for z in ztm_rail:
            d = haversine_m(s["lat"], s["lon"], z["lat"], z["lon"])
            if d < MERGE_RADIUS_M and (best is None or d < best[0]):
                best = (d, z)
        if best is None:
            continue
        if _norm_name(best[1]["name"]) == _norm_name(s["name"]):
            merged[s["id"]] = best[1]["id"]
        else:
            unmatched_near.append({"stop": s["id"], "name": s["name"], "ztm": best[1]["id"],
                                   "ztm_name": best[1]["name"], "distance_m": round(best[0])})
    # platforms follow their parent station
    for s in all_stops.values():
        if s["parent"] in merged:
            merged[s["id"]] = merged[s["parent"]]

    served = set(st["stop"].tolist())
    stops_out = []
    for sid, i in stop_index.items():
        s = all_stops[sid]
        s["group"] = _stop_group(s)
        s["modes"] = sorted({ROUTE_TYPES.get(t, str(t)) for t in served_types.get(i, ())})
        s["served"] = i in served
        s["same_as"] = merged.get(sid)
        s["platform"] = None
        s["members"] = []
        stops_out.append(s)
    stops_out += _rail_platforms(stops_out)
    for s in stops_out:
        # boarding = a location a trip can be boarded at: a served post / platform that is not folded into another
        s["boarding"] = bool(s["served"] and not s["same_as"] and not s["platform"]
                             and (s["location_type"] == 0 or s["members"]))

    # Every file is written atomically. The .npz goes last: _ensure_built() treats it as "cache is complete".
    save_json(DERIVED / "gtfs_stops.json", stops_out)
    save_json(DERIVED / "gtfs_trips.json", trips)
    save_json(DERIVED / "gtfs_merge.json", {"merged": merged, "unmatched_near": unmatched_near})
    save_json(DERIVED / "gtfs_frequencies.json", {str(k): v for k, v in freq.items()})
    save_npz(DERIVED / "gtfs_stop_times.npz", **st, runs=runs, trip_route_type=trip_route_type)


_BUILD_LOCK = threading.Lock()


def _ensure_built():
    """Build the cache once. Threads wait for each other, so only one runs the 25 s build."""
    with _BUILD_LOCK:
        _ensure_built_locked()


def _ensure_built_locked():
    npz = DERIVED / "gtfs_stop_times.npz"
    stops_path = DERIVED / "gtfs_stops.json"
    trips_path = DERIVED / "gtfs_trips.json"
    if not npz.exists() or not stops_path.exists() or not trips_path.exists():
        _build()
        return
    with np.load(npz) as z:
        dist = z["shape_dist"] if "shape_dist" in z.files else None
    # Old caches stored truncated kilometers (max about 20). Meters along a real trip are larger.
    if dist is None or (len(dist) and int(dist.max()) < 500):
        _build()
        return
    with open(stops_path, encoding="utf-8") as f:
        if '"zone"' not in f.read(800):
            _build()


@lru_cache
def stops() -> list[dict]:
    _ensure_built()
    return load_json(DERIVED / "gtfs_stops.json")


@lru_cache
def stops_by_id() -> dict:
    return {s["id"]: s for s in stops()}


@lru_cache
def trips() -> list:
    _ensure_built()
    return load_json(DERIVED / "gtfs_trips.json")


@lru_cache
def merge_info() -> dict:
    _ensure_built()
    return load_json(DERIVED / "gtfs_merge.json")


@lru_cache
def stop_times() -> dict:
    _ensure_built()
    with np.load(DERIVED / "gtfs_stop_times.npz") as z:
        return {k: z[k] for k in z.files}


@lru_cache
def frequencies() -> dict:
    _ensure_built()
    return {int(k): v for k, v in load_json(DERIVED / "gtfs_frequencies.json").items()}


def warm() -> None:
    """Load every cache the routing endpoints use (build files on the first run). Called once at server start."""
    stops_by_id()
    trips()
    merge_info()
    frequencies()
    services()
    routes()
    _trip_ids()
    _trip_bounds()
    _rows_by_stop()
    _brigades()
    _stop_ids()
    _shapes()
    fare_table()
    _pairs()


def canonical(stop_id: str) -> str:
    s = stops_by_id()[stop_id]
    return s["platform"] or s["same_as"] or stop_id


def vertices() -> list[dict]:
    """Transit graph vertices: boarding locations (posts, rail platforms, metro platforms, stations with trips
    that have no platform)."""
    return [s for s in stops() if s["boarding"]]


@lru_cache
def _pairs():
    """Adjacent stop pairs inside each trip: arrays (from_idx, to_idx, trip_idx)."""
    st = stop_times()
    same_trip = st["trip"][1:] == st["trip"][:-1]
    adjacent = same_trip & (st["pos"][1:] - st["pos"][:-1] >= 1)
    # pkp rows outside the area were removed; only keep rows that were adjacent in the original trip
    pkp_mask = np.array([t[0].startswith("pkp:") for t in trips()])[st["trip"][1:]]
    adjacent &= ~pkp_mask | (st["pos"][1:] - st["pos"][:-1] == 1)
    idx = np.nonzero(adjacent)[0]
    return idx, idx + 1


@lru_cache(maxsize=4)
def edges(date_str: str | None = None) -> dict:
    """Stop -> next stop edges. Returns counts and the unique (from, to, route) list."""
    st = stop_times()
    tr = trips()
    ids = [s["id"] for s in stops()]
    pos = {sid: n for n, sid in enumerate(ids)}
    canon_idx = np.array([pos[canonical(sid)] for sid in ids], dtype=np.int32)
    a, b = _pairs()
    fr, to = canon_idx[st["stop"][a]], canon_idx[st["stop"][b]]
    trip_i = st["trip"][a]
    keep = fr != to
    fr, to, trip_i = fr[keep], to[keep], trip_i[keep]

    route_names = [t[1] for t in tr]
    uniq_route = {(f, t, route_names[k]) for f, t, k in zip(fr.tolist(), to.tolist(), trip_i.tolist())}
    uniq_pair = {(f, t) for f, t, _ in uniq_route}
    result = {
        "unique_from_to_route": len(uniq_route),
        "unique_from_to": len(uniq_pair),
    }
    if date_str:
        svc = services()
        active = np.array([date_str in svc.get(t[2], ()) for t in tr])
        runs = st["runs"]
        result["timetable_edges_on_date"] = int((runs[trip_i] * active[trip_i]).sum())
        result["date"] = date_str
    result["list"] = [{"from": ids[f], "to": ids[t], "route": r} for f, t, r in sorted(uniq_route)]
    return result


@lru_cache
def _stop_ids() -> list[str]:
    return [s["id"] for s in stops()]


@lru_cache
def _trip_ids() -> dict[str, int]:
    return {t[0]: i for i, t in enumerate(trips())}


@lru_cache
def _trip_bounds() -> np.ndarray:
    """Row span [start, end) of each trip inside stop_times, which are grouped by trip."""
    trip = stop_times()["trip"]
    bounds = np.full((len(trips()), 2), -1, dtype=np.int32)
    if len(trip) == 0:
        return bounds
    cuts = np.flatnonzero(trip[1:] != trip[:-1]) + 1
    starts = np.r_[0, cuts]
    ends = np.r_[cuts, len(trip)]
    bounds[trip[starts]] = np.column_stack((starts, ends))
    return bounds


@lru_cache
def _rows_by_stop() -> dict[int, np.ndarray]:
    """Stop-array index -> row numbers in stop_times. Built once so departures are not a full scan."""
    st = stop_times()["stop"]
    if len(st) == 0:
        return {}
    order = np.argsort(st, kind="mergesort")
    ordered = st[order]
    cuts = np.flatnonzero(ordered[1:] != ordered[:-1]) + 1
    starts = np.r_[0, cuts]
    ends = np.r_[cuts, len(st)]
    return {int(ordered[a]): order[a:b] for a, b in zip(starts, ends)}


def _targets(stop_id: str) -> list[int]:
    """Array indexes of a stop and of the stops folded into it (merged rail station, platform children)."""
    return [i for i, s in enumerate(stops()) if s["id"] == stop_id or s["same_as"] == stop_id
            or s["platform"] == stop_id]


def departures(stop_id: str, date_str: str, after_sec: int, limit: int = 20) -> list[dict]:
    st = stop_times()
    tr = trips()
    rts = routes()
    svc = services()
    if stop_id not in stops_by_id():
        raise KeyError(stop_id)
    chunks = [_rows_by_stop().get(i, np.array([], dtype=np.int64)) for i in _targets(stop_id)]
    rows = np.concatenate(chunks) if chunks else np.array([], dtype=np.int64)
    freq = frequencies()
    bounds = _trip_bounds()
    out = []
    for r in rows:
        ti = int(st["trip"][r])
        trip_id, route_id, service_id, block = tr[ti][:4]
        if date_str not in svc.get(service_id, ()):
            continue
        offsets = [0]
        if ti in freq:  # frequency-based template (metro): expand runs
            base = int(st["dep"][bounds[ti, 0]])
            offsets = [s - base + k * hw for s, e, hw in freq[ti] for k in range(max(1, (e - s) // hw))]
        headsign = tr[ti][4] if len(tr[ti]) > 4 else ""
        wheelchair = tr[ti][5] if len(tr[ti]) > 5 else ""
        for off in offsets:
            dep = int(st["dep"][r]) + off
            if dep >= after_sec:
                route = rts[route_id]
                out.append({"time": f"{dep // 3600:02d}:{dep % 3600 // 60:02d}:{dep % 60:02d}",
                            "sec": dep, "line": route["short_name"], "mode": route["mode"],
                            "route_id": route_id, "trip_id": trip_id, "brigade": block,
                            "headsign": headsign, "wheelchair": wheelchair, "feed": route["feed"]})
    out.sort(key=lambda d: d["sec"])
    return out[:limit]


def whole_trip(trip_id: str, board_stop: str, board_sec: int) -> list[dict]:
    """Every call of the trip, timed so `board_stop` departs at `board_sec`."""
    return trip_onward(trip_id, board_stop, board_sec, whole=True)


def trip_onward(trip_id: str, board_stop: str, board_sec: int, whole: bool = False) -> list[dict]:
    """Stops of one trip from the boarding call onward, times shifted to `board_sec`.

    The first item is the boarding stop. Stop ids are canonical (merged rail platforms
    point at the station they were merged into).
    """
    ti = _trip_ids().get(trip_id)
    if ti is None:
        return []
    start, end = (int(x) for x in _trip_bounds()[ti])
    if start < 0:
        return []
    st = stop_times()
    ids = _stop_ids()
    by_id = stops_by_id()
    best = None
    for r in range(start, end):
        sid = ids[int(st["stop"][r])]
        stop = by_id[sid]
        if sid == board_stop or stop.get("same_as") == board_stop:
            dep = int(st["dep"][r])
            if dep <= board_sec and (best is None or dep > best[0]):
                best = (dep, r)
    if best is None:
        return []
    offset = board_sec - best[0]
    out = []
    for r in range(start if whole else best[1], end):
        sid = ids[int(st["stop"][r])]
        stop = by_id[sid]
        out.append({
            "stop_id": stop["same_as"] or sid,
            "name": stop["name"],
            "lat": stop["lat"],
            "lon": stop["lon"],
            "arr": int(st["arr"][r]) + offset,
            "dep": int(st["dep"][r]) + offset,
            "zone": stop.get("zone") or "",
            "shape_dist": int(st["shape_dist"][r]),
            "wheelchair": stop.get("wheelchair") or "",
        })
    return out


def trip_shape_id(trip_id: str) -> str:
    ti = _trip_ids().get(trip_id)
    if ti is None:
        return ""
    trip = trips()[ti]
    return trip[6] if len(trip) > 6 else ""


@lru_cache
def _shapes() -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """shape id (feed prefix) -> (distance m, lat, lon), sorted by distance."""
    out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for feed in FEEDS:
        try:
            rows = list(_rows(feed, "shapes.txt"))
        except KeyError:
            continue
        current = None
        bucket_d, bucket_lat, bucket_lon = [], [], []

        def flush():
            if current and bucket_d:
                order = np.argsort(np.array(bucket_d))
                out[current] = (np.array(bucket_d, dtype=np.float64)[order],
                                np.array(bucket_lat, dtype=np.float64)[order],
                                np.array(bucket_lon, dtype=np.float64)[order])

        for row in rows:
            key = f"{feed}:{row['shape_id']}"
            if key != current:
                flush()
                current = key
                bucket_d, bucket_lat, bucket_lon = [], [], []
            bucket_d.append(float(_shape_dist(row.get("shape_dist_traveled"))))
            bucket_lat.append(float(row["shape_pt_lat"]))
            bucket_lon.append(float(row["shape_pt_lon"]))
        flush()
    return out


def shape_slice(shape_id: str, dist_from: int, dist_to: int) -> list[list[float]]:
    """Shape points between two distances along a trip. Empty when the shape or the distances are missing."""
    if not shape_id or dist_from < 0 or dist_to <= dist_from:
        return []
    pack = _shapes().get(shape_id)
    if pack is None:
        return []
    dist, lat, lon = pack
    i = int(np.searchsorted(dist, dist_from, side="left"))
    j = int(np.searchsorted(dist, dist_to, side="right"))
    i = min(max(i, 0), len(dist) - 1)
    j = min(max(j, i + 1), len(dist))
    return [[round(float(lat[k]), 6), round(float(lon[k]), 6)] for k in range(i, j)]


def _load_fares(feed: str) -> list[dict]:
    """One feed's fare_attributes. A fare with no rules is feed-wide (WKD)."""
    rules_zones: dict[str, set] = defaultdict(set)
    rules_routes: dict[str, set] = defaultdict(set)
    for rule in _rows(feed, "fare_rules.txt"):
        if rule.get("contains_id"):
            rules_zones[rule["fare_id"]].add(rule["contains_id"])
        if rule.get("route_id"):
            rules_routes[rule["fare_id"]].add(rule["route_id"])
    out = []
    for fare in _rows(feed, "fare_attributes.txt"):
        duration = fare.get("transfer_duration") or ""
        transfers = fare.get("transfers") or ""
        out.append({
            "id": fare["fare_id"],
            "price": float(fare["price"]),
            "duration_s": int(duration) if duration else None,
            "transfers": int(transfers) if transfers else None,
            "zones": rules_zones.get(fare["fare_id"], set()),
            "routes": rules_routes.get(fare["fare_id"], set()),
        })
    return out


@lru_cache
def fare_table() -> list[dict]:
    """ZTM fares from warsaw.zip: price, max duration, zones the fare contains, routes it is limited to."""
    return _load_fares("ztm")


@lru_cache
def fare_table_for(feed: str) -> list[dict]:
    """Fares of one feed. WKD has prices and durations and no zones. KM has no fare file."""
    return _load_fares(feed)


@lru_cache
def plk_ids() -> dict[str, str]:
    """`pkp:<stop_id>` -> PLK station id, for the live operations feed."""
    out = {}
    for row in _rows("pkp", "stops.txt"):
        plk = row.get("plk_secondary_id") or ""
        if plk:
            out[f"pkp:{row['stop_id']}"] = plk
    return out


@lru_cache
def transfer_links() -> tuple:
    """`(from_id, to_id, min_seconds)` from every feed's transfers.txt. Type 3 is skipped.

    Stop ids wear the feed prefix (`pkp:...`). A missing min time becomes 60 seconds.
    """
    out = []
    for feed in FEEDS:
        for row in _rows(feed, "transfers.txt"):
            if row.get("transfer_type") == "3":
                continue
            raw = row.get("min_transfer_time") or ""
            out.append((f"{feed}:{row['from_stop_id']}", f"{feed}:{row['to_stop_id']}", int(raw) if raw else 60))
    return tuple(out)


@lru_cache
def pathway_links(step_free: bool = False) -> tuple:
    """`(from_id, to_id, meters, seconds)` from pathways.txt. Stairs and escalators drop when step-free.

    Warsaw extracts have no pathways.txt today, so this is empty until a feed grows one.
    """
    out = []
    for feed in FEEDS:
        for row in _rows(feed, "pathways.txt"):
            mode = row.get("pathway_mode") or ""
            if step_free and mode in {"2", "4"}:
                continue
            length = float(row.get("length") or 0)
            sec = int(row.get("traversal_time") or 0) or max(30, int(length))
            a, b = f"{feed}:{row['from_stop_id']}", f"{feed}:{row['to_stop_id']}"
            out.append((a, b, length, sec))
            if row.get("is_bidirectional", "1") != "0":
                out.append((b, a, length, sec))
    return tuple(out)


@lru_cache
def _brigades() -> dict[tuple[str, str], list[int]]:
    rts = routes()
    out: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, trip in enumerate(trips()):
        out[(rts[trip[1]]["short_name"], trip[3])].append(i)
    return out


def headsign_for(line: str, brigade: str, date_str: str, at_sec: int) -> str:
    """Headsign of the GTFS trip with this line and brigade running at `at_sec`. Empty when none matches."""
    svc = services()
    st = stop_times()
    bounds = _trip_bounds()
    found = ""
    for ti in _brigades().get((line, brigade), ()):
        trip = trips()[ti]
        if date_str not in svc.get(trip[2], ()):
            continue
        start, end = (int(x) for x in bounds[ti])
        if start < 0:
            continue
        if int(st["dep"][start]) <= at_sec <= int(st["arr"][end - 1]):
            return trip[4] if len(trip) > 4 else ""
        found = trip[4] if len(trip) > 4 else found
    return found


@lru_cache
def _max_segment_s() -> np.ndarray:
    """Longest scheduled time between two consecutive stops of each trip (s); 0 for trips with one stop."""
    st = stop_times()
    out = np.zeros(len(trips()), dtype=np.int32)
    if len(st["trip"]) < 2:
        return out
    same = st["trip"][1:] == st["trip"][:-1]
    seg = (st["arr"][1:] - st["dep"][:-1]).astype(np.int32)
    np.maximum.at(out, st["trip"][1:][same], seg[same])
    return out


def _service_days(when: datetime) -> list[tuple[str, float, int]]:
    """(service date, epoch of its midnight, seconds since that midnight) for today and yesterday.

    Yesterday covers trips after midnight (GTFS times past 24:00).
    """
    out = []
    for back in (0, 1):
        day = when.date() - timedelta(days=back)
        midnight = datetime.combine(day, datetime.min.time())
        out.append((day.strftime("%Y%m%d"), clock.warsaw_epoch(midnight), int((when - midnight).total_seconds())))
    return out


def max_segment_for(line: str, brigade: str, when: datetime) -> int | None:
    """Longest scheduled stop-to-stop time (s) of the trip this brigade runs at `when`; None when no trip runs."""
    svc = services()
    st = stop_times()
    bounds = _trip_bounds()
    for date_str, _, sec in _service_days(when):
        for ti in _brigades().get((line, brigade), ()):
            start, end = (int(x) for x in bounds[ti])
            if start < 0 or date_str not in svc.get(trips()[ti][2], ()):
                continue
            if int(st["dep"][start]) <= sec <= int(st["arr"][end - 1]):
                return int(_max_segment_s()[ti])
    return None


@lru_cache(maxsize=4096)
def _trip_static(ti: int) -> tuple | None:
    """(stops with seconds since service midnight, shape (metres, lat, lon)) of a trip; None without a shape.

    Distances are computed here from the coordinates: GTFS shape_dist_traveled is in km in warsaw.zip and
    `_shape_dist` keeps only whole units. Each stop is placed on the nearest shape point at or after the
    previous stop's point.
    """
    shape = _shapes().get(trips()[ti][6] if len(trips()[ti]) > 6 else "")
    start, end = (int(x) for x in _trip_bounds()[ti])
    if shape is None or start < 0 or len(shape[1]) < 2:
        return None
    _, lat, lon = shape
    la, lo = np.radians(lat), np.radians(lon)
    step = 2 * 6371000.0 * np.arcsin(np.sqrt(np.sin(np.diff(la) / 2) ** 2
                                             + np.cos(la[:-1]) * np.cos(la[1:]) * np.sin(np.diff(lo) / 2) ** 2))
    metres = np.r_[0.0, np.cumsum(step)]
    st = stop_times()
    ids = _stop_ids()
    by_id = stops_by_id()
    out = []
    j = 0
    for r in range(start, end):
        stop = by_id[ids[int(st["stop"][r])]]
        dy = (lat[j:] - stop["lat"]) * 111195.0
        dx = (lon[j:] - stop["lon"]) * 111195.0 * np.cos(np.radians(stop["lat"]))
        j += int(np.argmin(dx * dx + dy * dy))
        out.append({"id": stop["id"], "name": stop["name"], "lat": stop["lat"], "lon": stop["lon"],
                    "dist": float(metres[j]), "dep": int(st["dep"][r]), "arr": int(st["arr"][r])})
    return out, (metres, lat, lon)


def brigade_trips(line: str, brigade: str, when: datetime, window_s: int) -> list[dict]:
    """Trips of a line + brigade running at `when` +- `window_s`, in the form of algorithms/bus_delay.py.

    Times become epoch seconds. Trips without a shape are left out.
    """
    svc = services()
    out = []
    for date_str, midnight, sec in _service_days(when):
        for ti in _brigades().get((line, brigade), ()):
            trip = trips()[ti]
            if date_str not in svc.get(trip[2], ()):
                continue
            static = _trip_static(ti)
            if static is None:
                continue
            stops_, shape = static
            if not stops_[0]["dep"] - window_s <= sec <= stops_[-1]["arr"] + window_s:
                continue
            out.append({"trip_id": trip[0], "headsign": trip[4] if len(trip) > 4 else "",
                        "start": midnight + stops_[0]["dep"], "end": midnight + stops_[-1]["arr"],
                        "shape": shape,
                        "stops": [{"id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
                                   "dist": s["dist"], "sched": midnight + s["dep"]} for s in stops_]})
    return out


def route_stops(route_id: str) -> list[list[str]]:
    """Distinct stop sequences (variants) of a route."""
    st = stop_times()
    tr = trips()
    ids = [s["id"] for s in stops()]
    tis = [i for i, t in enumerate(tr) if t[1] == route_id]
    if not tis:
        raise KeyError(route_id)
    mask = np.isin(st["trip"], tis)
    variants = defaultdict(list)
    for t, s in zip(st["trip"][mask], st["stop"][mask]):
        variants[int(t)].append(ids[s])
    return sorted({tuple(v) for v in variants.values()}, key=len, reverse=True)


def reference_date() -> str:
    """First Wednesday that all feeds cover, starting today (a normal weekday)."""
    svc = services()
    d = date.today()
    for _ in range(60):
        ds = d.strftime("%Y%m%d")
        if d.weekday() == 2 and all(any(ds in v for k, v in svc.items() if k.startswith(f + ":"))
                                    for f in FEEDS):
            return ds
        d += timedelta(days=1)
    return date.today().strftime("%Y%m%d")


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/gtfs", tags=["mkuran GTFS"])


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    """'min_lat,min_lon,max_lat,max_lon' -> tuple. 422 when it is not four numbers in order."""
    try:
        box = tuple(float(x) for x in text.split(","))
    except ValueError:
        box = ()
    if len(box) != 4 or box[0] > box[2] or box[1] > box[3]:
        raise HTTPException(422, "bbox must be min_lat,min_lon,max_lat,max_lon (four numbers, min <= max)")
    return box


@router.get("/stops")
def api_stops(mode: str | None = Query(None, description="bus, tram, metro, rail"),
              feed: str | None = Query(None, description="ztm, wkd, pkp"),
              bbox: str | None = Query(None, description="min_lat,min_lon,max_lat,max_lon"),
              include_merged: bool = False):
    """Boarding points (posts / platforms). Merged duplicates are hidden unless include_merged."""
    box = parse_bbox(bbox) if bbox else BBOX
    out = []
    for s in stops():
        if not (s["boarding"] or (include_merged and s["served"] and s["location_type"] == 0)):
            continue
        if mode and mode not in s["modes"]:
            continue
        if feed and s["feed"] != feed:
            continue
        if not in_bbox(s["lat"], s["lon"], box):
            continue
        out.append(s)
    return out


@router.get("/stops/{stop_id}")
def api_stop(stop_id: str):
    """One stop with group, modes and same_as (merged rail station)."""
    s = stops_by_id().get(stop_id)
    if not s:
        raise HTTPException(404, "unknown stop_id (use the feed prefix, e.g. ztm:700901)")
    return s


@router.get("/stop-groups")
def api_stop_groups(feed: str | None = None):
    """Stop groups (ZTM zespół, station parents) with their posts."""
    groups = defaultdict(list)
    for s in stops():
        if s["boarding"] and (not feed or s["feed"] == feed):
            groups[s["group"]].append(s["id"])
    names = stops_by_id()
    return [{"group": g, "name": names[p[0]]["name"], "posts": p} for g, p in groups.items()]


@router.get("/routes")
def api_routes(mode: str | None = None, feed: str | None = None):
    """Lines from all GTFS feeds (SKM only from ZTM)."""
    return [r for r in routes().values()
            if (not mode or r["mode"] == mode) and (not feed or r["feed"] == feed)]


@router.get("/routes/{route_id}/stops")
def api_route_stops(route_id: str):
    """Distinct stop sequences (variants) of one line."""
    try:
        return {"route": routes()[route_id], "variants": route_stops(route_id)}
    except KeyError:
        raise HTTPException(404, "unknown route_id (use the feed prefix, e.g. ztm:131)") from None


@router.get("/stops/{stop_id}/departures")
def api_departures(stop_id: str,
                   date_: str | None = Query(None, alias="date", description="YYYYMMDD", pattern=r"^\d{8}$"),
                   time: str | None = Query(None, description="HH:MM", pattern=r"^\d{1,2}:\d{2}$"),
                   limit: int = Query(20, ge=1, le=200)):
    """Next departures from a stop (all feeds; a merged rail station includes KM / IC trains)."""
    now = clock.warsaw_now()
    d = date_ or now.strftime("%Y%m%d")
    t = time or now.strftime("%H:%M")
    try:
        return departures(stop_id, d, _sec(t + ":00"), limit)
    except KeyError:
        raise HTTPException(404, "unknown stop_id") from None


@router.get("/edges")
def api_edges(limit: int = Query(1000, ge=1, le=10000), offset: int = Query(0, ge=0)):
    """Unique stop -> next stop edges per route (canonical stop ids)."""
    e = edges()
    return {"total": e["unique_from_to_route"], "items": e["list"][offset:offset + limit]}


@router.get("/merge")
def api_merge():
    """Rail stations merged across feeds, and near misses (< 150 m, different names)."""
    return merge_info()
