"""StationLocations: every transport node (bus / tram post, metro platform, rail platform or station, Veturilo
station) with one position and one representation shared by the C++ router, the backend and the frontend.

Built once from GTFS (mkuran), Veturilo (GBFS) and OSM (osm.transport_objects): GTFS decides what exists and is the
fallback position; an exact OSM match (ref = ZTM stop id, platform number, nearest subway entrance) moves the node
to the real object. Rules: algorithms/station_map.py. Output: data/derived/stations.json (+ stations_report.json),
documented in algorithms/router/README.md ("StationLocations").

Usage (from backend/): uv run python stations.py      # rebuild and print the report
"""
import sys
import time
from collections import Counter, defaultdict
from functools import lru_cache

from config import DERIVED, GTFS_DIR, REPO, load_json, save_json
from sources import mkuran, nextbike, osm

sys.path.insert(0, str(REPO / "algorithms"))
from station_map import (  # noqa: E402
    ENTRANCE_MAX_M, PLATFORM_MAX_M, POST_MAX_M, match_entrance, match_posts, match_rail_platform, overlay_hash,
    parse_platform_code,
)
from street_model import JUNCTION_RADIUS_M  # noqa: E402

FILE = DERIVED / "stations.json"
REPORT = DERIVED / "stations_report.json"
METRO_TRANSFER_M = 200       # walk between two platforms of one metro station (in-station transfer)
METRO_PLATFORM_MAX_M = 100   # a subway platform way this close to the GTFS platform gives its position


def model_constants() -> dict:
    """Everything outside the locations that changes a street path. Part of the overlay hash."""
    return {"speed": osm.SPEED, "walk_speed": osm.WALK_SPEED, "bike_speed": osm.BIKE_SPEED, "wait": osm.WAIT,
            "elevator_s": osm.ELEVATOR_S, "metro_access_m": osm.METRO_ACCESS_M, "metro_transfer_m": METRO_TRANSFER_M,
            "no_steps": sorted(osm.NO_STEPS),
            "access_k": osm.ACCESS_K, "access_extra_m": osm.ACCESS_EXTRA_M, "max_snap_m": osm.MAX_SNAP_M,
            "junction_radius_m": JUNCTION_RADIUS_M, "ramp_tags": {m: list(t) for m, t in osm.RAMP_TAGS.items()},
            "match_m": {"post": POST_MAX_M, "platform": PLATFORM_MAX_M, "entrance": ENTRANCE_MAX_M,
                        "metro_platform": METRO_PLATFORM_MAX_M}}


def _kind(s: dict) -> str:
    if s["id"].startswith("vet:"):
        return "veturilo"
    if "metro" in s["modes"]:
        return "metro_platform"
    if s["feed"] in ("pkp", "wkd"):
        return "rail_platform" if s["code"].startswith("peron") else "rail_station"
    return "tram_post" if s["modes"] == ["tram"] else "bus_post"


def _location(s: dict, kind: str) -> dict:
    return {"id": s["id"], "kind": kind, "name": s["name"], "code": s.get("code", ""), "modes": s["modes"],
            "feed": s["feed"], "position": {"lat": s["lat"], "lon": s["lon"]}, "source": "gtfs", "osm": None,
            "gtfs": {"lat": s["lat"], "lon": s["lon"]}, "members": s.get("members", []), "group": s.get("group"),
            "parent": s.get("parent"), "entrances": [], "transfers": [], "wheelchair": s.get("wheelchair", ""),
            "zone": s.get("zone", "")}


def _place(loc: dict, match: dict, osm_type: str, matched_by: str) -> None:
    loc["position"] = {"lat": match["lat"], "lon": match["lon"]}
    loc["source"] = "osm"
    loc["osm"] = {"type": osm_type, "id": match["osm_id"], "matched_by": matched_by,
                  "distance_m": match["distance_m"]}


def build() -> dict:
    t0 = time.time()
    objs = osm.transport_objects()
    nodes, ways = objs["nodes"], objs["ways"]
    entrances_osm = [n for n in nodes if n["tags"].get("railway") == "subway_entrance"]
    subway_ways = [w for w in ways if w["tags"].get("subway") == "yes"]
    rail_ways = [w for w in ways if w["tags"].get("subway") != "yes" and w["tags"].get("train") != "no"
                 and w["tags"].get("bus") != "yes" and w["tags"].get("tram") != "yes"]
    stops = mkuran.stops_by_id()
    report = {"kinds": Counter(), "matched": Counter(), "mismatches": [], "entrances": Counter()}

    locations = []
    for s in mkuran.vertices():
        loc = _location(s, _kind(s))
        locations.append(loc)
        report["kinds"][loc["kind"]] += 1

    # bus / tram posts: exact ref
    posts = [l for l in locations if l["kind"] in ("bus_post", "tram_post") and l["feed"] == "ztm"]
    matched, mismatches = match_posts([{"id": l["id"], "raw_id": stops[l["id"]]["raw_id"], **l["gtfs"]} for l in posts],
                                      nodes)
    for l in posts:
        if l["id"] in matched:
            _place(l, matched[l["id"]], "node", "ref")
            report["matched"][l["kind"]] += 1
    report["mismatches"] += mismatches

    # metro platforms: entrances of the station (GTFS location_type 2) matched to OSM subway entrances;
    # the platform position from the nearest subway platform way; in-station transfers between platforms
    by_parent = defaultdict(list)
    for s in stops.values():
        if s["location_type"] == 2 and s["parent"]:
            by_parent[s["parent"]].append(s)
    metro = [l for l in locations if l["kind"] == "metro_platform"]
    for l in metro:
        for e in by_parent.get(l["parent"], []):
            m = match_entrance(e["lat"], e["lon"], entrances_osm)
            l["entrances"].append({"gtfs_id": e["id"], "lat": m["lat"] if m else e["lat"],
                                   "lon": m["lon"] if m else e["lon"], "osm_id": m["osm_id"] if m else None})
            report["entrances"]["osm" if m else "gtfs"] += 1
        best = None
        for w in subway_ways:
            c = sum(p[0] for p in w["coords"]) / len(w["coords"]), sum(p[1] for p in w["coords"]) / len(w["coords"])
            d = mkuran.haversine_m(l["gtfs"]["lat"], l["gtfs"]["lon"], *c)
            if d <= METRO_PLATFORM_MAX_M and (best is None or d < best[2]):
                best = (w, c, d)
        if best:
            w, c, d = best
            _place(l, {"osm_id": w["id"], "lat": c[0], "lon": c[1], "distance_m": round(d, 1)}, "way",
                   "nearest_subway_platform")
            report["matched"]["metro_platform"] += 1
        l["transfers"] = [{"to": o["id"], "walk_m": METRO_TRANSFER_M} for o in metro
                          if o["parent"] == l["parent"] and o["id"] != l["id"]]

    # rail platforms: platform number (local_ref, "peron N", track in ref)
    for l in [l for l in locations if l["kind"] == "rail_platform"]:
        number = l["code"].removeprefix("peron ")
        tracks = {parse_platform_code(stops[m]["code"])[1] for m in l["members"] if parse_platform_code(stops[m]["code"])}
        m = match_rail_platform(l["gtfs"]["lat"], l["gtfs"]["lon"], number, tracks, rail_ways)
        if m:
            _place(l, m, "way", m["matched_by"])
            report["matched"]["rail_platform"] += 1
            if m.get("wheelchair") and not l["wheelchair"]:
                l["wheelchair"] = {"yes": "1", "no": "2"}.get(m["wheelchair"], "")

    for v in nextbike.stations():
        loc = _location({"id": v["id"], "name": v["name"], "code": v.get("number") or "", "modes": ["bike"],
                         "feed": "nextbike", "lat": v["lat"], "lon": v["lon"], "group": v["id"]}, "veturilo")
        loc["capacity"], loc["virtual"] = v.get("capacity"), v.get("virtual", False)
        locations.append(loc)
        report["kinds"]["veturilo"] += 1

    locations.sort(key=lambda l: l["id"])
    out = {"hash": overlay_hash(locations, model_constants()), "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "constants": model_constants(), "locations": locations}
    save_json(FILE, out)
    rep = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in report.items()}
    rep["total"] = len(locations)
    rep["seconds"] = round(time.time() - t0, 1)
    save_json(REPORT, rep)
    load.cache_clear()
    return rep


def stale() -> bool:
    """stations.json is missing or older than its inputs (GTFS cache, OSM objects, Veturilo file, this code)."""
    if not FILE.exists():
        return True
    inputs = [DERIVED / "gtfs_stop_times.npz", DERIVED / "osm_transport.json", osm.PBF, REPO / "backend" / "stations.py",
              REPO / "algorithms" / "station_map.py", *GTFS_DIR.glob("*.zip")]
    return FILE.stat().st_mtime < max((f.stat().st_mtime for f in inputs if f.exists()), default=0)


@lru_cache
def load() -> dict:
    if stale():
        build()
    return load_json(FILE)


def locations() -> list[dict]:
    return load()["locations"]


if __name__ == "__main__":
    print(build())
