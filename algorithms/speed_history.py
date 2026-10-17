"""Average speed from the user's own trips.

Pure functions, no I/O and nothing is stored. The app records a GPS track while the user rides a
planned route; `split_track` turns that track into per-mode records (distance, moving time, speed)
and the app keeps only those records on the device. `summarize` turns the records into an average
speed per mode.

Moving speed: time spent standing still (red lights, a break) and GPS gaps are not counted.
Records are made for walking (or wheelchair, see `walk_as`) and cycling only; public transport
speeds are not something the user can set.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Iterable, Mapping, Sequence

MODES = ("walking", "cycling", "wheelchair")

# A step shorter than this is "moving"; slower or with a longer gap it is a stop (not counted).
MIN_MOVING_KMH = 0.5
MAX_GAP_S = 60
# Faster than any of our modes: a GPS jump, the step is dropped.
JUMP_KMH = 60
# A leg needs at least this much to make a record.
MIN_DISTANCE_M = 200
MIN_MOVING_S = 60
# Plausible average speeds per mode (km/h), same as the allowed range of the speed setting.
SPEED_RANGE = {"walking": (1.0, 10.0), "cycling": (3.0, 45.0), "wheelchair": (1.0, 15.0)}
# The track must roughly match the planned route, otherwise the split by distance would be wrong.
MIN_MATCH, MAX_MATCH = 0.5, 2.0

MIN_TRIPS = 5
WINDOW = 20
# Records further than this share of the median from the median are ignored (outliers).
OUTLIER_SHARE = 0.5


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _moving_steps(points: Sequence[Mapping[str, float]]) -> list[tuple[float, float]]:
    """(distance m, time s) of every step that counts as moving."""
    pts = sorted(points, key=lambda p: p["t"])
    steps: list[tuple[float, float]] = []
    for a, b in zip(pts, pts[1:]):
        dt = b["t"] - a["t"]
        if dt <= 0 or dt > MAX_GAP_S:
            continue
        d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        kmh = d / dt * 3.6
        if MIN_MOVING_KMH <= kmh <= JUMP_KMH:
            steps.append((d, dt))
    return steps


def split_track(
    points: Sequence[Mapping[str, float]],
    legs: Sequence[Mapping[str, object]],
    walk_as: str = "walking",
    at: str = "",
) -> list[dict]:
    """Per-mode records of one trip.

    `points`: GPS samples `{lat, lon, t}` (t in seconds). `legs`: the planned route's legs
    `{mode, distanceM}` in order. The moving distance of the track is shared between the legs in
    proportion to their planned distance (the user followed the plan). Walking legs count as
    `walk_as` ("walking" or "wheelchair"), bike legs as "cycling"; other legs only take their share.
    Returns at most one record per mode, `[]` when the track is too short, does not match the plan
    or gives an implausible speed.
    """
    if walk_as not in ("walking", "wheelchair"):
        raise ValueError("walk_as must be 'walking' or 'wheelchair'")
    steps = _moving_steps(points)
    planned = sum(float(leg["distanceM"]) for leg in legs)
    travelled = sum(d for d, _ in steps)
    if planned <= 0 or travelled <= 0 or not MIN_MATCH <= travelled / planned <= MAX_MATCH:
        return []

    # upper bound (share of the moving distance) at which each leg ends
    bounds: list[float] = []
    acc = 0.0
    for leg in legs:
        acc += float(leg["distanceM"]) / planned
        bounds.append(acc)

    dist = [0.0] * len(legs)
    time = [0.0] * len(legs)
    cum = 0.0
    for d, dt in steps:
        share = (cum + d / 2) / travelled  # which leg the middle of the step falls into
        i = next((k for k, b in enumerate(bounds) if share <= b + 1e-9), len(legs) - 1)
        dist[i] += d
        time[i] += dt
        cum += d

    totals: dict[str, list[float]] = {}
    for leg, d, t in zip(legs, dist, time):
        mode = walk_as if leg["mode"] == "walk" else "cycling" if leg["mode"] == "bike" else None
        if mode:
            acc_mode = totals.setdefault(mode, [0.0, 0.0])
            acc_mode[0] += d
            acc_mode[1] += t

    records = []
    for mode, (d, t) in totals.items():
        if d < MIN_DISTANCE_M or t < MIN_MOVING_S:
            continue
        kmh = d / t * 3.6
        low, high = SPEED_RANGE[mode]
        if not low <= kmh <= high:
            continue
        records.append(
            {"mode": mode, "distanceM": round(d), "durationS": round(t), "kmh": round(kmh, 1), "at": at}
        )
    return records


def summarize(records: Iterable[Mapping[str, object]], min_trips: int = MIN_TRIPS, window: int = WINDOW) -> dict:
    """Average speed per mode from the latest `window` records of each mode.

    The average is total distance / total moving time of the records that are not outliers (further
    than half the median from the median, only judged when there are at least 5 records).
    `enough` says the app may use it as the speed setting (`min_trips` records or more).
    """
    result: dict[str, dict] = {}
    for mode in MODES:
        mine = sorted((r for r in records if r["mode"] == mode), key=lambda r: str(r.get("at", "")))[-window:]
        trips = len(mine)
        summary = {"trips": trips, "distanceKm": 0.0, "avgKmh": None, "medianKmh": None, "enough": trips >= min_trips}
        if trips:
            med = median(float(r["kmh"]) for r in mine)
            kept = [r for r in mine if abs(float(r["kmh"]) - med) <= OUTLIER_SHARE * med] if trips >= 5 else mine
            distance = sum(float(r["distanceM"]) for r in kept)
            seconds = sum(float(r["durationS"]) for r in kept)
            summary["distanceKm"] = round(distance / 1000, 1)
            summary["medianKmh"] = round(med, 1)
            summary["avgKmh"] = round(distance / seconds * 3.6, 1) if seconds > 0 else None
        result[mode] = summary
    return result
