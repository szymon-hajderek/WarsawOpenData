"""Route options: transit trips from the router's RAPTOR (`POST /plan`), street-only trips from `POST /route`.

Every router leg goes through `legs_from_router`; positions come from the StationLocations overlay and transit
geometry from GTFS shapes (`geometry.py`). There is no Python transit planner: while the router's timetable or the
mode's plan is not ready, `POST /api/routes` answers 503. Timetable times only (no live delay shift).
"""
from __future__ import annotations

import contextvars
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from config import REPO, haversine_m

sys.path.insert(0, str(REPO / "algorithms"))
from districts import blocked  # noqa: E402
from plan_trip import as_warsaw, warsaw_offset  # noqa: E402

log = logging.getLogger("uvicorn.error")

import street_router
from sources import alerts

from ..models import Place, Profile, RouteLeg, RouteOption, RouteSegment
from . import geometry
from .engine import RouteEngine
from .geo import format_time, round_half_up

OSM_SPEED = {"walk": 1.3, "bike": 4.2}
PROFILE_SPEED = {
    "standard": {"walk": 1.3, "bike": 4.2},
    "slow": {"walk": 0.9, "bike": 3.0},
    "accessible": {"walk": 1.0, "bike": 0.0},
    "stroller": {"walk": 1.0, "bike": 0.0},
}
_SPEED = contextvars.ContextVar("route_speed", default=None)
_BLOCK = contextvars.ContextVar("route_block", default=None)
_EXCLUDE = contextvars.ContextVar("route_exclude", default=frozenset())
_MIN_BIKES = contextvars.ContextVar("route_min_bikes", default=0)
_WALK_MODE = contextvars.ContextVar("route_walk_mode", default=None)


_overlay = geometry.overlay
_loc = geometry.location
_pos = geometry.pos


def _distance(a, b) -> float:
    return haversine_m(a[0], a[1], b[0], b[1])


def _minutes(seconds: float) -> int:
    if seconds <= 0:
        return 0
    return max(1, round_half_up(seconds / 60))


class RealRouteEngine(RouteEngine):
    def update_state(self, update: dict[str, Any]) -> None:
        return None

    def query_routes(self, frm: Place, to: Place, profile: Profile, when: str | None = None, search=None) -> list[RouteOption]:
        return self._routes(frm, to, profile, _clock(when), search)

    def query_from_stop(self, stop_id: str, to: Place, profile: Profile, at: datetime, search=None) -> list[RouteOption]:
        """Transit options from a stop (StationLocations id) leaving at `at` (naive Warsaw time); /plan gets the id."""
        found = _loc(stop_id)
        if not found:
            raise LookupError(f"unknown stop {stop_id}")
        frm = Place(id=stop_id, label=found.get("name") or stop_id,
                    position=(found["position"]["lat"], found["position"]["lon"]))
        return self._routes(frm, to, profile, at, search, plan_from=stop_id)

    def _routes(self, frm, to, profile, now, search, plan_from=None) -> list[RouteOption]:
        travel = getattr(search, "travel", "transit")
        if travel in ("accessible", "stroller"):
            profile = travel
        speed, accessible, max_transfers, block = _limits(profile, search)
        origin = tuple(frm.position)
        dest = tuple(to.position)
        graph = "accessible" if accessible else "stroller" if profile == "stroller" else "walk"
        exclude = frozenset(getattr(search, "excludeModes", None) or ())
        if travel == "transit" and getattr(search, "access", "walk") == "bike":
            graph = "bike"  # own bike to, from and between stops, carried on transit; /plan has no Veturilo then
            if speed["bike"] <= 0:
                speed["bike"] = OSM_SPEED["bike"]  # bikeKmh 0 only switches Veturilo off
        elif travel == "transit" and "veturilo" in exclude:
            speed["bike"] = 0.0  # no rented bike; an own-bike trip (travel=bike) is not affected
        tokens = (_SPEED.set(speed), _BLOCK.set(block), _WALK_MODE.set(graph), _EXCLUDE.set(exclude),
                  _MIN_BIKES.set(getattr(search, "minBikes", None) or 0))
        try:
            if travel != "transit":
                option = self._street_option(frm, to, origin, dest, profile, now, travel)
                return [option] if _option_clear(option) else []
            if not _plan_ready(graph):
                raise street_router.RouteError(503, "transit timetable not ready")
            try:
                return self._plan(frm, to, profile, now, plan_from or origin, dest, graph, speed, max_transfers)
            except NotImplementedError as exc:
                raise street_router.RouteError(503, f"transit timetable not ready: {exc}") from exc
            except street_router.RouteError as exc:
                if exc.status in (404, 422):
                    return []  # a point off the street graph: nothing connects
                raise
        finally:
            _SPEED.reset(tokens[0])
            _BLOCK.reset(tokens[1])
            _WALK_MODE.reset(tokens[2])
            _EXCLUDE.reset(tokens[3])
            _MIN_BIKES.reset(tokens[4])

    def _plan(self, frm, to, profile, now, origin, dest, mode, speed, max_transfers) -> list[RouteOption]:
        """Transit options planned by RAPTOR in the router (POST /plan), plus one later query for more departures."""
        date, sec = street_router.service_time(now)
        options = _plan_options(speed, max_transfers, profile)
        raws = street_router.plan(origin, dest, mode, date=date, time=sec, **options)
        departures = [raw["dep_s"] for raw in raws if _counted(raw)]
        if departures and len(raws) < MAX_OPTIONS:
            raws += street_router.plan(origin, dest, mode, date=date, time=int(min(departures)) + 60, **options)
        built = [self._plan_option(raw, frm.label, to.label, origin, dest, date, profile) for raw in raws]
        if all(_counted(raw) for raw in raws) and not isinstance(origin, str):  # no street-only trip: walk
            built.append(self._walk_option(frm, to, origin, dest, profile, now))
        result = _finish(built)
        if not result and not isinstance(origin, str):
            # No transit option at all (every mode excluded, or nothing runs): the street-only trip is the answer,
            # however long, instead of an empty list.
            fallback = self._walk_option(frm, to, origin, dest, profile, now, limit=False)
            if fallback is not None:
                fallback.tags.append("Bez komunikacji")
                result = [fallback]
        return result

    def _plan_option(self, raw, from_label, to_label, origin, dest, date, profile) -> Optional[RouteOption]:
        """One /plan option -> RouteOption (None for an empty or too long street-only trip)."""
        if not raw.get("legs") or (not _counted(raw) and raw["seconds"] > 50 * 60):
            return None
        legs = legs_from_router(raw, from_name=from_label, to_name=to_label, points=(origin, dest))
        leave = datetime.strptime(date, "%Y%m%d") + timedelta(seconds=raw["dep_s"])
        option = _option(_plan_id(legs), _plan_title(legs), legs, leave, raw["seconds"])
        option.transfers = int(raw.get("transfers", option.transfers))
        _street_tags(option, raw, profile)
        lines = {leg.line for leg in legs if leg.mode not in geometry.STREET_MODES}
        if lines & alerts.alerted_lines():
            option.tags.append("Zmiana na trasie")
        return option

    def _walk_option(self, frm, to, origin, dest, profile, now, limit=True) -> Optional[RouteOption]:
        """The street-only trip next to transit options. `limit`: only when it is short (<= 5 km, <= 50 min), so it
        does not crowd the list; without a limit it is the fallback when no transit option exists at all."""
        if limit and _distance(origin, dest) > 5000:
            return None
        bike = _WALK_MODE.get() == "bike"  # transit with the own bike: the street-only trip is ridden
        street = _street(origin, dest, "bike" if bike else "walk", profile)
        if street is None or (limit and _seconds(street) > 50 * 60):
            return None
        legs = legs_from_router(street, from_name=frm.label, to_name=to.label, points=(origin, dest))
        option_id, title = ("bike", "Własny rower") if bike else ("walk", "Pieszo")
        return _street_tags(_option(option_id, title, legs, now, _seconds(street)), street, profile)

    def _street_option(self, frm, to, origin, dest, profile, now, travel):
        mode = "bike" if travel == "bike" else "walk"
        street = _street(origin, dest, mode, profile, strict=True)
        if street is None:
            raise ValueError("cycling is disabled by the selected profile or speed")
        legs = legs_from_router(street, from_name=frm.label, to_name=to.label, points=(origin, dest))
        title = {"walk": "Pieszo", "accessible": "Wózek inwalidzki",
                 "stroller": "Wózek dziecięcy", "bike": "Własny rower"}[travel]
        return _street_tags(_option("street-" + travel, title, legs, now, _seconds(street)), street, profile)

MAX_OPTIONS = 6


def _plan_ready(mode: str) -> bool:
    """True when the router's timetable and the mode's plan are ready (GET /health); else log and say no."""
    health = street_router.health()
    timetable = (health.get("timetable") or {}).get("status")
    plan = (health.get("plan") or {}).get(mode)
    if timetable == "ok" and plan == "ok":
        return True
    log.warning("route engine: /plan not ready for %s (timetable %s, plan %s): 503",
                mode, timetable, plan)
    return False


def _plan_options(speed, max_transfers, profile) -> dict:
    """The /plan keys from the preferences: speeds, counted legs, no Veturilo when cycling is off, min_bikes."""
    options = {"speeds": _router_speeds(profile), "max_legs": max_transfers + 1}
    if speed["bike"] <= 0:
        options["veturilo_s"] = 0
    if _EXCLUDE.get():
        options["exclude_modes"] = sorted(_EXCLUDE.get())
    if _MIN_BIKES.get():
        options["min_bikes"] = _MIN_BIKES.get()
    return options


def _counted(raw: dict) -> bool:
    """A /plan option with a transit ride or a Veturilo rental (not the street-only trip)."""
    return any(leg["mode"] not in ("walk", "bike") for leg in raw.get("legs") or [])


def _ridden(leg: RouteLeg) -> bool:
    """An own-bike leg that is really ridden (not only pushed, e.g. an in-station metro transfer)."""
    return leg.mode == "bike" and bool(leg._street_distances and leg._street_distances[1] > 0)


def _plan_title(legs: list[RouteLeg]) -> str:
    """Rides and rentals ("16 + M1", "Veturilo + 502"); with the own bike its ridden legs too ("Rower + 502 + Rower")."""
    counted = any(leg.mode not in ("walk", "bike") for leg in legs)
    parts = [("Veturilo" if leg.mode == "veturilo" else "Rower" if leg.mode == "bike" else leg.line or leg.mode)
             for leg in legs if leg.mode != "walk" and (leg.mode != "bike" or (counted and _ridden(leg)))]
    parts = [part for i, part in enumerate(parts) if part != "Rower" or i == 0 or parts[i - 1] != "Rower"]
    return " + ".join(parts) or ("Własny rower" if any(leg.mode == "bike" for leg in legs) else "Pieszo")


def _plan_id(legs: list[RouteLeg]) -> str:
    """`pt-<trip id>-...` (POST /api/live/route-delays reads it), else `bike` (Veturilo or own bike only) or `walk`."""
    trips = [leg.tripId for leg in legs if leg.tripId]
    if trips:
        return "pt-" + "-".join(trips)
    return "bike" if any(leg.mode in ("veturilo", "bike") for leg in legs) else "walk"


def _finish(built: list[Optional[RouteOption]]) -> list[RouteOption]:
    """Drop empty options and those crossing an excluded area, dedupe, sort by duration, keep MAX_OPTIONS, tag."""
    out, seen = [], set()
    for option in sorted((o for o in built if o is not None), key=lambda o: o.durationMin):
        key = tuple((leg.mode, leg.line, leg.fromId, leg.toId, leg.tripId) for leg in option.legs)
        if any(leg.tripId for leg in option.legs):
            key += (option.departure,)  # frequency-based metro runs share the template's trip id
        if key in seen or not _option_clear(option):
            continue
        seen.add(key)
        out.append(option)
    out = out[:MAX_OPTIONS]
    _tag(out)
    return out


def _limits(profile: Profile, search):
    """Speeds in m/s, whether to skip steps, how many transfers, and what to avoid."""
    speed = dict(PROFILE_SPEED[profile])
    accessible = profile == "accessible"
    max_transfers = 2
    districts: list[str] = []
    points: list[tuple[float, float, float]] = []
    if search is not None:
        if getattr(search, "walkKmh", None):
            speed["walk"] = search.walkKmh / 3.6
        if getattr(search, "bikeKmh", None) is not None:
            speed["bike"] = search.bikeKmh / 3.6
        body_obj = getattr(search, "body", None)
        if body_obj is not None and body_obj.wheelchair != "none":
            accessible = True
            speed["bike"] = 0.0
        if getattr(search, "stepFree", False):
            accessible = True
        if getattr(search, "maxTransfers", None) is not None:
            max_transfers = search.maxTransfers
        districts = list(getattr(search, "excludedDistricts", []) or [])
        points = [(p.position[0], p.position[1], p.radiusM) for p in (getattr(search, "excludedPoints", None) or [])]
    block = (districts, points) if districts or points else None
    if profile in ("accessible", "stroller"):
        speed["bike"] = 0.0
    return speed, accessible, max_transfers, block


def _inside(lat, lon) -> bool:
    spec = _BLOCK.get()
    if not spec or lat is None or lon is None:
        return False
    return blocked(float(lat), float(lon), spec[0], spec[1], _distance)


def _option_clear(option: RouteOption) -> bool:
    """False when the option uses an excluded mode (the safety net) or its path enters an excluded area."""
    if any(leg.mode in _EXCLUDE.get() for leg in option.legs):
        return False
    for leg in option.legs:
        for point in leg.path[1:-1]:
            if _inside(point[0], point[1]):
                return False
    return True


def _clock(when: str | None) -> datetime:
    """Naive Warsaw wall time. `when` is ``HH:MM`` or an ISO datetime; empty means now."""
    if not when:
        utc = datetime.now(timezone.utc)
        return (utc + warsaw_offset(utc)).replace(tzinfo=None)
    text = when.strip()
    try:
        if len(text) == 5 and text[2] == ":":
            hour, minute = text.split(":")
            current = _clock(None)
            return current.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("when must be HH:MM or an ISO datetime") from exc
    return as_warsaw(parsed)


def _router_mode(mode, profile):
    if mode == "walk":
        return _WALK_MODE.get() or (profile if profile in ("accessible", "stroller") else "walk")
    return mode


def _router_speeds(profile):
    table = _SPEED.get() or PROFILE_SPEED[profile]
    return {"walk": table["walk"], "bike": table["bike"] or OSM_SPEED["bike"]}


def _street(a, b, mode: str, profile: Profile, *, strict=False):
    table = _SPEED.get() or PROFILE_SPEED[profile]
    speed = table[mode]
    if speed <= 0:
        return None
    try:
        return street_router.route(a, b, _router_mode(mode, profile), speeds=_router_speeds(profile))
    except street_router.RouteError as exc:
        if strict or exc.status not in (404, 422):
            raise
        return None


def _end_id(endpoint):
    """Station id of a router leg end: `{"id", "lonlat"}` (old format), an id string or None (new format)."""
    return endpoint.get("id") if isinstance(endpoint, dict) else endpoint


def _end_fallback(endpoint, query_point):
    """What a leg end without an overlay position stands for: the query point, else the old format's lonlat."""
    if query_point is not None:
        return query_point
    if isinstance(endpoint, dict) and endpoint.get("lonlat"):
        lon, lat = endpoint["lonlat"]
        return lat, lon
    return None


def _seconds(answer: dict) -> float:
    """Door-to-door seconds of a router answer, from its legs (the new format has no top-level totals)."""
    return sum(leg["seconds"] for leg in answer["legs"])


def _points(answer: dict, key: str) -> list:
    """Elevators / steps of an answer: from its legs, else the old format's top-level list."""
    legs = answer.get("legs") or []
    if any(key in leg for leg in legs):
        return [point for leg in legs for point in leg.get(key) or []]
    return list(answer.get(key) or [])


def _latlon(points) -> list[tuple[float, float]]:
    return [(lat, lon) for lon, lat in points or []]


def legs_from_router(answer: dict, names: dict[str, str] | None = None, *,
                     from_name="", to_name="", rented=False, points=(None, None)) -> list[RouteLeg]:
    """The one adapter from router legs (old and new format) to `RouteLeg`.

    Leg ends are `{"id", "lonlat"}` (old) or an id / None (new; None = the query's own start / end). `points` =
    what the router was asked for (coordinates or ids) and stands for a None end. Street (walk, bike, veturilo)
    and transit legs; top-level totals are not needed."""
    names = names or {}
    out = []
    raw_legs = answer["legs"]
    single = len(raw_legs) == 1
    for index, raw in enumerate(raw_legs):
        start_id, end_id = _end_id(raw["from"]), _end_id(raw["to"])
        query_from = points[0] if index == 0 else None
        query_to = points[1] if index == len(raw_legs) - 1 else None

        def label(station_id, fallback):
            if station_id in names:
                return names[station_id]
            if fallback:
                return fallback
            location = _loc(station_id)
            return location["name"] if location else ""

        def end(station_id, endpoint, query_point):
            # Router geometry is rounded to 5 decimals; marker metadata keeps the exact catalog position.
            lat_lon = geometry.position(station_id, _end_fallback(endpoint, query_point))
            return (lat_lon[1], lat_lon[0]) if lat_lon else None

        mode = "veturilo" if rented and raw["mode"] == "bike" else raw["mode"]
        street = mode in geometry.STREET_MODES
        path, approximate = geometry.leg_path({**raw, "from": start_id, "to": end_id}, query_from, query_to)
        path = [tuple(point) for point in path]
        if street:
            meters = raw["walk_m"] + raw["bike_m"]
            seconds = raw["seconds"]
        else:
            meters = sum(_distance(a, b) for a, b in zip(path, path[1:]))
            seconds = raw["arr_s"] - raw["dep_s"] if "arr_s" in raw and "dep_s" in raw else raw["seconds"]
        if street:
            # The old format has elevators / steps only at the top level (one leg).
            extra = {key: _latlon(raw.get(key, answer.get(key) if single else None)) for key in ("elevators", "steps")}
        else:
            extra = {"waitS": raw.get("wait_s"), "tripId": raw.get("trip_id")}
        leg = RouteLeg(
            mode=mode, from_=label(start_id, from_name if index == 0 else ""),
            to=label(end_id, to_name if index == len(raw_legs) - 1 else ""),
            line=raw.get("line"), durationMin=_minutes(seconds), distanceM=round(meters, 1),
            path=path, start=end(start_id, raw["from"], query_from), end=end(end_id, raw["to"], query_to),
            fromId=start_id, toId=end_id, approximatePath=approximate,
            segments=[RouteSegment(kind=s["kind"], path=_latlon(s["path"]), lengthM=s["length_m"])
                      for s in raw.get("segments", [])],
            **extra,
        )
        if street:
            leg._street_distances = (raw["walk_m"], raw["bike_m"])
            leg._street_wait = raw.get("wait_s") or 0.0
        out.append(leg)
    return out


def _street_tags(option, answer, profile):
    mode = _router_mode("walk", profile)
    if all(leg.mode == "walk" for leg in option.legs) and mode in ("accessible", "stroller"):
        option.tags.append("schody tylko z rynnami" if mode == "stroller" and _points(answer, "steps") else "bez schodów")
    elevators = _points(answer, "elevators")
    if elevators:
        option.tags.append(f"windy: {len(elevators)}")
    return option


def _option(option_id, title, legs, leave, door_s: float | None = None) -> RouteOption:
    transit = sum(1 for leg in legs if leg.mode not in ("walk", "bike", "veturilo"))
    duration = _minutes(door_s) if door_s is not None else sum(leg.durationMin for leg in legs)
    return RouteOption(
        id=option_id, title=title, legs=legs,
        departure=format_time(leave), arrival=format_time(leave + timedelta(minutes=duration)),
        durationMin=duration, distanceM=round(sum(leg.distanceM for leg in legs), 1),
        transfers=max(0, transit - 1), tags=[],
    )


def _tag(options: list[RouteOption]) -> None:
    if options:
        options[0].tags.append("Najszybsza")
