"""Trips from the vehicle the user is in (`RouteRequest.onboard`). Timetable only: no live delays (user decision).

The live side only says which GTFS trip the vehicle runs and where it is (`bus_detect._delay_for`; its delay is
ignored). The next two stops of that trip are planning origins at their **scheduled** arrival (`/plan` with
`from` = the stop id). Every option gets a ride leg from the vehicle's position to that stop prepended; when the
plan stays on the same trip, the two rides merge into one leg.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import street_router
from config import haversine_m
from sources import mkuran

from ..models import Place, Profile, RouteLeg, RouteOption
from . import geometry
from .geo import format_time
from .real_engine import MAX_OPTIONS, RealRouteEngine, _minutes, _plan_id

ORIGINS = 2  # next stops of the trip used as planning origins
HERE = "Obecna pozycja"


class VehicleNotFound(LookupError):
    """Unknown vehicle, no GTFS trip, or no stop of the trip ahead."""


def _live(vehicle_id: str) -> dict:
    """{trip_id, line, mode, next_stop, scheduled, position} of a live vehicle (no delay)."""
    import bus_detect

    bus_detect._need_data()  # 503 without live data (no PORTAL_KEY), like the other live endpoints
    info = bus_detect._delay_for(vehicle_id)
    if not info or not info.get("tripId"):
        raise VehicleNotFound(vehicle_id)
    with bus_detect._lock:
        history = list(bus_detect._history.get(vehicle_id, ()))
    nxt = info.get("nextStop") or {}
    return {"trip_id": info["tripId"], "line": info.get("line"), "mode": info.get("mode") or "bus",
            "next_stop": nxt.get("id"), "scheduled": nxt.get("scheduled"),
            "position": (history[-1]["lat"], history[-1]["lon"]) if history else None}


def _scheduled_calls(trip_id: str) -> list[dict]:
    """Every call of a trip at its scheduled times (seconds after the service day's midnight)."""
    ti = mkuran._trip_ids().get(trip_id)
    if ti is None:
        return []
    start = int(mkuran._trip_bounds()[ti][0])
    if start < 0:
        return []
    st = mkuran.stop_times()
    first = mkuran._stop_ids()[int(st["stop"][start])]
    return mkuran.trip_onward(trip_id, first, int(st["dep"][start]), whole=True)


def _hms(text: str) -> int:
    h, m, s = (int(x) for x in text.split(":"))
    return h * 3600 + m * 60 + s


def next_index(calls: list[dict], next_stop: str | None, scheduled: str | None, now_sec: int) -> int | None:
    """Index of the next stop: the live next stop at its scheduled time, else the first call after now."""
    if next_stop and scheduled:
        day_sec = _hms(scheduled) % 86400
        for i, call in enumerate(calls):
            if call["stop_id"] == next_stop and call["dep"] % 86400 == day_sec:
                return i
    return next((i for i, call in enumerate(calls) if call["arr"] > now_sec), None)


def _ride_leg(live: dict, calls: list[dict], i: int, now_sec: int) -> RouteLeg:
    """The ride from the vehicle's position to calls[i] on the GTFS shape (from the previous stop)."""
    stop = calls[i]
    part = calls[max(0, i - 1):i + 1]
    path, approximate = geometry.leg_path(
        {"mode": live["mode"], "trip_id": live["trip_id"], "from": part[0]["stop_id"], "to": stop["stop_id"]},
        calls=part)
    here = live["position"]
    if here is not None and path:
        nearest = min(range(len(path)), key=lambda k: haversine_m(here[0], here[1], path[k][0], path[k][1]))
        path = [list(here)] + path[nearest + 1:]
        if len(path) < 2:
            path.append(list(geometry.pos(stop["stop_id"], (stop["lat"], stop["lon"]))))
    end = geometry.pos(stop["stop_id"], (stop["lat"], stop["lon"]))
    meters = sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(path, path[1:]))
    return RouteLeg(
        mode=live["mode"] if live["mode"] in ("bus", "tram", "metro", "rail") else "bus",
        from_=HERE, to=stop.get("name") or stop["stop_id"], line=live["line"],
        durationMin=_minutes(stop["arr"] - now_sec), distanceM=round(meters, 1), path=[tuple(p) for p in path],
        start=(path[0][1], path[0][0]) if path else None, end=(end[1], end[0]),
        fromId=None, toId=stop["stop_id"], approximatePath=approximate, waitS=0.0, tripId=live["trip_id"])


def _merge(ride: RouteLeg, option: RouteOption, trip_id: str) -> tuple[list[RouteLeg], bool]:
    """[ride] + the option's legs; when the option stays on the same trip, the two rides become one leg."""
    legs = list(option.legs)
    k = 0
    while k < len(legs) and legs[k].mode == "walk" and legs[k].distanceM < 1:
        k += 1  # a zero-length walk at the stop does not count
    if k < len(legs) and legs[k].tripId == trip_id:
        same = legs[k]
        merged = ride.model_copy(update={
            "to": same.to, "toId": same.toId, "end": same.end, "path": ride.path + same.path[1:],
            "durationMin": ride.durationMin + same.durationMin + _minutes(same.waitS or 0),
            "distanceM": round(ride.distanceM + same.distanceM, 1),
            "approximatePath": ride.approximatePath or same.approximatePath})
        return [merged] + legs[k + 1:], True
    return [ride] + legs, False


def _arrival(option: RouteOption, at: datetime) -> datetime:
    hh, mm = (int(x) for x in option.arrival.split(":"))
    arrival = at.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return arrival + timedelta(days=1) if arrival < at - timedelta(minutes=1) else arrival


def query_onboard(engine: RealRouteEngine, vehicle_id: str, to: Place, profile: Profile, now: datetime,
                  search=None) -> list[RouteOption]:
    """Options from the vehicle `vehicle_id` (as in POST /api/live/nearest-buses) to `to`, departing now."""
    live = _live(vehicle_id)
    date, now_sec = street_router.service_time(now)
    midnight = datetime.strptime(date, "%Y%m%d")
    calls = _scheduled_calls(live["trip_id"])
    i = next_index(calls, live["next_stop"], live["scheduled"], now_sec)
    if i is None:
        raise VehicleNotFound(vehicle_id)
    built = []
    for j in range(i, min(i + ORIGINS, len(calls))):
        stop = calls[j]
        at = midnight + timedelta(seconds=stop["arr"])
        ride = _ride_leg(live, calls, j, now_sec)
        try:
            planned = engine.query_from_stop(stop["stop_id"], to, profile, at, search)
        except LookupError:  # a stop missing from the StationLocations overlay
            continue
        for option in planned:
            legs, merged = _merge(ride, option, live["trip_id"])
            counted = any(leg.mode not in ("walk", "bike") for leg in option.legs)
            title = option.title if merged else f"{live['line']} + {option.title}" if counted else live["line"]
            arrival = _arrival(option, at)
            built.append((arrival, RouteOption(
                id=_plan_id(legs), title=title, legs=legs, departure=format_time(now), arrival=format_time(arrival),
                durationMin=max(0, round((arrival - now).total_seconds() / 60)),
                distanceM=round(sum(leg.distanceM for leg in legs), 1),
                transfers=option.transfers if merged else option.transfers + 1 if counted else 0,
                tags=[tag for tag in option.tags if tag != "Najszybsza"])))
    out, seen = [], set()
    for _, option in sorted(built, key=lambda item: (item[0], item[1].durationMin, len(item[1].legs))):
        key = tuple((leg.mode, leg.line, leg.fromId, leg.toId, leg.tripId) for leg in option.legs)
        if key in seen or option.id in {o.id for o in out}:
            continue
        seen.add(key)
        out.append(option)
    out = out[:MAX_OPTIONS]
    if out:
        out[0].tags.append("Najszybsza")
    return out
