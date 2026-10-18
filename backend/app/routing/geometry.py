"""Leg shapes for rendering only; routing never reads them.

The router answers station ids only (`null` = the query's own start / end), so positions come from the
StationLocations overlay (`stations.json`). A leg's path is the router's street path, the GTFS shape of a ride,
or, when neither gives two points, a polyline through the named points (`approximate`).
"""
from __future__ import annotations

import functools

import stations
from sources import mkuran

STREET_MODES = ("walk", "bike", "veturilo")


@functools.lru_cache(maxsize=1)
def overlay() -> dict[str, dict]:
    return {location["id"]: location for location in stations.locations()}


def location(stop_id):
    return overlay().get(stop_id) if stop_id else None


def pos(stop_id, fallback):
    """(lat, lon) of a StationLocations id, else `fallback`."""
    found = location(stop_id)
    if found:
        return found["position"]["lat"], found["position"]["lon"]
    return fallback


def position(point_id, query_point):
    """(lat, lon) of a leg end: an id -> its overlay position; None -> `query_point`.

    `query_point` may itself be an id or a (lat, lon) pair (what the caller asked the router for)."""
    if isinstance(query_point, str):
        query_point = pos(query_point, None)
    elif query_point is not None:
        query_point = (query_point[0], query_point[1])
    if point_id is None:
        return query_point
    return pos(point_id, query_point)


def _latlon(points) -> list[list[float]]:
    return [[lat, lon] for lon, lat in points or []]


def _ride_path(trip_id, calls) -> list[list[float]]:
    """GTFS shape of one ride by stop distances, else the shape with the stops projected on it; [] if none."""
    if not trip_id or len(calls) < 2:
        return []
    try:
        shape_id = mkuran.trip_shape_id(trip_id)
    except (KeyError, OSError, ValueError):
        return []
    try:
        shape = mkuran.shape_slice(shape_id, calls[0].get("shape_dist", -1), calls[-1].get("shape_dist", -1))
    except (KeyError, OSError, ValueError):
        shape = []
    if len(shape) >= 2:
        return shape
    try:
        shape = mkuran.shape_by_stops(shape_id, calls)
    except (KeyError, OSError, ValueError):
        shape = []
    return shape if len(shape) >= 2 else []


def _router_calls(raw: dict) -> list[dict]:
    """mkuran calls of a router transit leg (trip_id + stops), cut at `to`; else the stops at overlay positions."""
    stops = raw.get("stops") or []
    trip_id = raw.get("trip_id")
    if trip_id and stops:
        try:
            calls = mkuran.trip_onward(trip_id, stops[0]["id"], int(stops[0].get("dep_s", raw.get("dep_s", 0))))
        except (KeyError, OSError, ValueError, TypeError):
            calls = []
        ids = [call.get("stop_id") for call in calls]
        if raw.get("to") in ids:
            return calls[:ids.index(raw["to"]) + 1]
    out = []
    for stop in stops:
        lat_lon = pos(stop["id"], None)
        if lat_lon:
            out.append({"stop_id": stop["id"], "lat": lat_lon[0], "lon": lat_lon[1]})
    return out


def leg_path(raw: dict, query_from=None, query_to=None, calls=None) -> tuple[list[list[float]], bool]:
    """(path [[lat, lon]], approximate) of one leg.

    `raw` is a router leg (street, veturilo or transit) or `{"mode", "trip_id", "from", "to"}` with mkuran `calls`.
    `query_from` / `query_to` stand for a `null` end. Fewer than 2 points from the builder -> a polyline through
    `from`, every stop / call and `to`, flagged approximate."""
    if raw.get("mode") in STREET_MODES:
        path = _latlon(raw.get("path"))
    else:
        if calls is None:
            calls = _router_calls(raw)
        path = _ride_path(raw.get("trip_id"), calls)
    if len(path) >= 2:
        return path, False
    ids = [stop["id"] for stop in raw.get("stops") or []]
    points = [position(_end_id(raw.get("from")), query_from)]
    if calls:
        points += [pos(call.get("stop_id"), (call["lat"], call["lon"])) for call in calls]
    else:
        points += [pos(stop_id, None) for stop_id in ids]
    points.append(position(_end_id(raw.get("to")), query_to))
    line: list[list[float]] = []
    for point in points:
        if point is not None and (not line or line[-1] != list(point)):
            line.append(list(point))
    return line, True


def _end_id(endpoint):
    return endpoint.get("id") if isinstance(endpoint, dict) else endpoint
