"""GTFS -> OSM matching rules for transport nodes, and the overlay hash. Pure functions, no I/O.

GTFS is the authority: a location exists because GTFS has it; OSM only moves it to the real object when the
match is exact (an id or a platform number) and close. Everything else stays at the GTFS position.
Used by backend/stations.py; documented in algorithms/router/README.md ("StationLocations").
"""
import hashlib
import json
import math
import re

POST_MAX_M = 50.0        # an OSM post node with the same ref must be this close to the GTFS point
PLATFORM_MAX_M = 50.0    # a rail platform way must come this close to the GTFS platform position
PLATFORM_SEARCH_M = 300.0
ENTRANCE_MAX_M = 30.0    # a metro entrance node vs the GTFS entrance

_R = 6371000.0


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(a))


def _xy(lat, lon, lat0):
    return math.radians(lon) * _R * math.cos(math.radians(lat0)), math.radians(lat) * _R


def distance_to_way_m(lat, lon, coords) -> float:
    """Distance from a point to a polyline (metres, local projection)."""
    px, py = _xy(lat, lon, lat)
    pts = [_xy(a, b, lat) for a, b in coords]
    best = min(math.hypot(px - x, py - y) for x, y in pts)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            continue
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)))
    return best


def way_centre(coords) -> tuple[float, float]:
    return sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)


def match_posts(posts, osm_nodes, max_m=POST_MAX_M):
    """Bus / tram posts by exact `ref` = ZTM stop id. `posts`: [{id, raw_id, lat, lon}]; `osm_nodes`: OSM nodes with
    tags. Returns ({post id: {"osm_id", "lat", "lon", "distance_m"}}, [mismatches]). A platform node wins over a
    stop_position; the closest wins among equals. A far match (> max_m) is a mismatch, and the post keeps GTFS."""
    by_ref = {}
    for n in osm_nodes:
        ref = n["tags"].get("ref")
        if ref:
            rank = 0 if n["tags"].get("public_transport") == "platform" or n["tags"].get("highway") == "bus_stop" else 1
            by_ref.setdefault(ref, []).append((rank, n))
    matched, mismatches = {}, []
    for p in posts:
        cands = by_ref.get(p["raw_id"])
        if not cands:
            continue
        best = min(cands, key=lambda c: (c[0], haversine_m(p["lat"], p["lon"], c[1]["lat"], c[1]["lon"])))[1]
        d = haversine_m(p["lat"], p["lon"], best["lat"], best["lon"])
        if d <= max_m:
            matched[p["id"]] = {"osm_id": best["id"], "lat": best["lat"], "lon": best["lon"], "distance_m": round(d, 1)}
        else:
            mismatches.append({"id": p["id"], "osm_id": best["id"], "distance_m": round(d), "why": "ref too far"})
    return matched, mismatches


_PLATFORM_TRACK = re.compile(r"^\s*([0-9]+[A-Za-z]?(?:/[0-9]+)?)\s*t\.\s*([0-9]+[A-Za-z]?)\s*$")


def parse_platform_code(code: str):
    """GTFS PKP platform_code "2 t. 20" -> ("2", "20"); None when the child has no platform (FALLBACK etc.)."""
    m = _PLATFORM_TRACK.match(code or "")
    return (m.group(1), m.group(2)) if m else None


def group_rail_children(children):
    """PKP children of one station -> {platform number: [children]}; children without a platform -> key None."""
    groups = {}
    for c in children:
        parsed = parse_platform_code(c.get("code", ""))
        groups.setdefault(parsed[0] if parsed else None, []).append(c)
    return groups


def _platform_number_from_name(name: str):
    m = re.search(r"peron\s*([0-9]+[a-z]?)", (name or "").lower())
    return m.group(1) if m else None


def match_rail_platform(lat, lon, number, tracks, osm_ways, search_m=PLATFORM_SEARCH_M, max_m=PLATFORM_MAX_M):
    """One GTFS platform (number, its tracks, mean position) -> the OSM platform way, or None.
    Rules in order: local_ref = number; name "peron <number>"; a track number in ref ("10;12").
    The way must lie within search_m (centre) and come within max_m of the position."""
    near = [w for w in osm_ways if haversine_m(lat, lon, *way_centre(w["coords"])) <= search_m]
    rules = (
        ("local_ref", lambda t: t.get("local_ref") == number),
        ("name", lambda t: _platform_number_from_name(t.get("name")) == number),
        ("track", lambda t: bool(tracks & set(re.split(r"[;,]\s*", t.get("ref", ""))))),
    )
    for how, ok in rules:
        hits = [w for w in near if ok(w["tags"])]
        if not hits:
            continue
        w = min(hits, key=lambda w: distance_to_way_m(lat, lon, w["coords"]))
        d = distance_to_way_m(lat, lon, w["coords"])
        if d <= max_m:
            c = way_centre(w["coords"])
            return {"osm_id": w["id"], "lat": c[0], "lon": c[1], "distance_m": round(d, 1), "matched_by": how,
                    "level": w["tags"].get("level"), "wheelchair": w["tags"].get("wheelchair")}
        return None  # a number match that is too far: do not fall through to a weaker rule
    return None


def match_entrance(lat, lon, osm_entrances, max_m=ENTRANCE_MAX_M):
    """The nearest OSM subway_entrance within max_m of a GTFS entrance, or None."""
    best = None
    for n in osm_entrances:
        d = haversine_m(lat, lon, n["lat"], n["lon"])
        if d <= max_m and (best is None or d < best["distance_m"]):
            best = {"osm_id": n["id"], "lat": n["lat"], "lon": n["lon"], "distance_m": round(d, 1)}
    return best


def overlay_hash(locations, constants: dict) -> str:
    """SHA-256 over the canonical JSON of the locations and the model constants that change paths.
    The same input always gives the same hash; any change in a position, an id or a constant changes it."""
    payload = json.dumps({"locations": locations, "constants": constants}, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()
