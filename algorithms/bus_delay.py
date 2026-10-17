"""How late is a bus or tram? Compare the time it passed its previous stop with the timetable.

Pure functions, no I/O. A point is a dict {"lat", "lon", "t"} with "t" in epoch seconds.

1. The server keeps a short buffer of each vehicle's positions (`add_point`). Between two feed points
   (about 10 s apart) it also stores the midpoint, so there is a point about every 5 s, unless the data
   had a break (a failed poll, or more than MAX_GAP_S between the points).
2. `match_trip` projects the vehicle on the shape of each GTFS trip of its line + brigade running about now
   (`project`, distance along the shape). A brigade runs many trips on the same shape, so among the trips
   the vehicle is near, the one whose timetable at that point (`sched_at`) is closest to now wins.
3. `previous_stop`: the last stop of the trip before that distance is K-1, the next one is K.
4. `pass_time`: the buffered point closest to K-1, only within `radius_m`. None = delay unavailable.
5. delay = pass time - scheduled departure at K-1 (negative = early); shown as the delay at K.

A trip is a dict {"trip_id", "headsign", "start", "end", "shape": (dist, lat, lon), "stops": [...]},
"start" / "end" in epoch seconds, a stop is {"id", "name", "lat", "lon", "dist", "sched"} with "dist"
= distance along the shape (m) and "sched" = scheduled departure (epoch s).
"""
import math

from nearest_buses import haversine_m

MAX_GAP_S = 25  # the feed changes about every 10 s; a longer gap means data was missing
MATCH_M = 100  # the vehicle must be this close to the trip shape
WINDOW_S = 15 * 60  # trips running now +- this are candidates (a late trip may run past its end)
_M_PER_DEG = math.pi * 6371000.0 / 180


def add_point(buffer: list[dict], point: dict, broken: bool, keep_s: float) -> list[dict]:
    """Append a feed point (and the midpoint before it), drop points older than `keep_s`. Changes `buffer`.

    Midpoints have "mid": True. The last item is always a feed point. `broken` = a poll failed since
    the previous feed point, so no midpoint is added.
    """
    if buffer and point["t"] <= buffer[-1]["t"]:
        return buffer  # the same position again
    if buffer and not broken and point["t"] - buffer[-1]["t"] <= MAX_GAP_S:
        prev = buffer[-1]
        buffer.append({"lat": (prev["lat"] + point["lat"]) / 2, "lon": (prev["lon"] + point["lon"]) / 2,
                       "t": (prev["t"] + point["t"]) / 2, "mid": True})
    buffer.append({"lat": point["lat"], "lon": point["lon"], "t": point["t"], "mid": False})
    cutoff = point["t"] - keep_s
    drop = 0
    while drop < len(buffer) - 1 and buffer[drop]["t"] < cutoff:
        drop += 1
    del buffer[:drop]
    return buffer


def project(shape, lat: float, lon: float, prev_dist: float | None = None,
            max_m: float = MATCH_M) -> tuple[float, float] | None:
    """(distance along the shape m, distance from the shape m) of a point, None when farther than `max_m`.

    `shape` = (dist, lat, lon) sequences. A shape can pass the same place twice (loops): every stretch of
    the shape within `max_m` gives one candidate; with `prev_dist` the candidate closest to it wins,
    else the nearest one.
    """
    dist, slat, slon = shape
    n = len(dist)
    if n == 0:
        return None
    kx = _M_PER_DEG * math.cos(math.radians(lat))
    xs = [(float(o) - lon) * kx for o in slon]
    ys = [(float(a) - lat) * _M_PER_DEG for a in slat]
    if n == 1:
        off = math.hypot(xs[0], ys[0])
        return (float(dist[0]), off) if off <= max_m else None

    candidates = []  # best (off, along) of each stretch within max_m
    best = None
    for i in range(n - 1):
        dx, dy = xs[i + 1] - xs[i], ys[i + 1] - ys[i]
        seg2 = dx * dx + dy * dy
        u = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(xs[i] * dx + ys[i] * dy) / seg2))
        off = math.hypot(xs[i] + u * dx, ys[i] + u * dy)
        if off <= max_m:
            along = float(dist[i]) + u * (float(dist[i + 1]) - float(dist[i]))
            if best is None or off < best[0]:
                best = (off, along)
        elif best is not None:
            candidates.append(best)
            best = None
    if best is not None:
        candidates.append(best)
    if not candidates:
        return None
    if prev_dist is None:
        off, along = min(candidates)
    else:
        off, along = min(candidates, key=lambda c: abs(c[1] - prev_dist))
    return along, off


def sched_at(stops: list[dict], along: float) -> float:
    """Scheduled time at a distance along the trip, linear between stops (clamped to the first / last stop)."""
    if along <= stops[0]["dist"]:
        return stops[0]["sched"]
    for a, b in zip(stops, stops[1:]):
        if along <= b["dist"]:
            span = b["dist"] - a["dist"]
            u = 0.0 if span <= 0 else (along - a["dist"]) / span
            return a["sched"] + u * (b["sched"] - a["sched"])
    return stops[-1]["sched"]


def match_trip(trips: list[dict], lat: float, lon: float, now: float, prev: dict | None = None,
               window_s: float = WINDOW_S, max_m: float = MATCH_M) -> tuple[dict, float] | None:
    """(trip, distance along its shape) of the trip the vehicle most likely runs.

    Candidates: trips running at `now` +- `window_s` whose shape is within `max_m`. The winner is the one
    whose timetable at the vehicle's position is closest to `now` (ties: nearer shape). `prev` =
    {"trip_id", "dist"} of the last estimate, used for loops on the same trip.
    """
    best = None
    for trip in trips:
        if not trip["stops"] or not trip["start"] - window_s <= now <= trip["end"] + window_s:
            continue
        prev_dist = prev["dist"] if prev and prev.get("trip_id") == trip["trip_id"] else None
        hit = project(trip["shape"], lat, lon, prev_dist, max_m)
        if hit is None:
            continue
        score = (abs(sched_at(trip["stops"], hit[0]) - now), hit[1])
        if best is None or score < best[0]:
            best = (score, trip, hit[0])
    return None if best is None else (best[1], best[2])


def previous_stop(stops: list[dict], along: float) -> int | None:
    """Index of stop K-1 (the last stop at or before `along`). None before the first or at the last stop."""
    k1 = None
    for i, s in enumerate(stops):
        if s["dist"] <= along:
            k1 = i
        else:
            break
    if k1 is None or k1 >= len(stops) - 1:
        return None
    return k1


def pass_time(buffer: list[dict], lat: float, lon: float, radius_m: float) -> float | None:
    """Time of the buffered point closest to (lat, lon), only within `radius_m`. None when no point is that close."""
    best = None
    for p in buffer:
        d = haversine_m(p["lat"], p["lon"], lat, lon)
        if d <= radius_m and (best is None or d < best[0]):
            best = (d, p["t"])
    return None if best is None else best[1]


def estimate(buffer: list[dict], trips: list[dict], radius_m: float, prev: dict | None = None) -> dict:
    """Delay of one vehicle from its buffer and its candidate trips.

    Returns {"available", "reason", "trip", "dist", "prev_index", "passed_at", "delay_s"}.
    `reason` is None, "no_trip", "outside_trip" or "no_pass_in_radius".
    """
    out = {"available": False, "reason": "no_trip", "trip": None, "dist": None,
           "prev_index": None, "passed_at": None, "delay_s": None}
    if not buffer:
        return out
    now = buffer[-1]
    hit = match_trip(trips, now["lat"], now["lon"], now["t"], prev)
    if hit is None:
        return out
    trip, along = hit
    out.update(trip=trip, dist=along, reason="outside_trip")
    k1 = previous_stop(trip["stops"], along)
    if k1 is None:
        return out
    out.update(prev_index=k1, reason="no_pass_in_radius")
    stop = trip["stops"][k1]
    t = pass_time(buffer, stop["lat"], stop["lon"], radius_m)
    if t is None:
        return out
    out.update(available=True, reason=None, passed_at=t, delay_s=round(t - stop["sched"]))
    return out
