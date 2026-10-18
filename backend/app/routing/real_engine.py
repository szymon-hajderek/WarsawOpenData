"""Routes from the parsed GTFS timetable, the OSM street graph and live Veturilo status.

Transit trips come from the router's RAPTOR (`POST /plan`, `_plan`); every leg goes through `legs_from_router`.
The Python planner below is the fallback while the router's timetable / plan is not ready (`/health`) or `/plan`
answers 501 / 503:
a walk, a Veturilo ride, Veturilo before or after one ride, Veturilo between two rides, a direct
ride and one transfer. A matched live bus or tram shifts the clock when it is behind schedule.
Street geometry comes from OSM for the options that are returned.
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
from lateness import lateness_s  # noqa: E402
from plan_trip import (  # noqa: E402
    as_warsaw, best_bike_pair, bike_access_pairs, bike_between, direct_rides, nearby, service_moment,
    spread_groups, transfer_rides, two_transfer_rides, warsaw_offset,
)

log = logging.getLogger("uvicorn.error")

import street_router
import stations
from sources import alerts, mkuran, nextbike, osm

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
WALK_M = {"standard": 900, "slow": 700, "accessible": 600, "stroller": 600}
CATCH_SLACK_S = 20
_SPEED = contextvars.ContextVar("route_speed", default=None)
_BLOCK = contextvars.ContextVar("route_block", default=None)
_EXCLUDE = contextvars.ContextVar("route_exclude", default=frozenset())
_WALK_MODE = contextvars.ContextVar("route_walk_mode", default=None)


_overlay = geometry.overlay
_loc = geometry.location
_pos = geometry.pos


def _mapped(record, id_key="id"):
    lat, lon = _pos(record[id_key], (record["lat"], record["lon"]))
    return {**record, "lat": lat, "lon": lon}


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
        now = _clock(when)
        date, now_sec = service_moment(now)
        travel = getattr(search, "travel", "transit")
        if travel in ("accessible", "stroller"):
            profile = travel
        speed, accessible, max_transfers, block = _limits(profile, search)
        origin = tuple(frm.position)
        dest = tuple(to.position)
        graph = "accessible" if accessible else "stroller" if profile == "stroller" else "walk"
        exclude = frozenset(getattr(search, "excludeModes", None) or ())
        if travel == "transit" and "veturilo" in exclude:
            speed["bike"] = 0.0  # no rented bike; an own-bike trip (travel=bike) is not affected
        tokens = (_SPEED.set(speed), _BLOCK.set(block), _WALK_MODE.set(graph), _EXCLUDE.set(exclude))
        try:
            if travel != "transit":
                option = self._street_option(frm, to, origin, dest, profile, now, travel)
                return [option] if _option_clear(option) else []
            if _plan_ready(graph):
                try:
                    return self._plan(frm, to, profile, now, origin, dest, graph, speed, max_transfers)
                except NotImplementedError as exc:
                    log.warning("route engine: /plan refused (%s); using the Python planner", exc)
                except street_router.RouteError as exc:
                    if exc.status in (404, 422):
                        return []  # a point off the street graph: nothing connects (as the Python planner)
                    if exc.status != 503:
                        raise
                    log.warning("route engine: /plan not ready (%s); using the Python planner", exc)
            self._vehicles = _live_vehicles()
            self._trip_delays = _trip_delays()
            self._station_delays = _station_delays()
            return self._query(frm, to, profile, now, now_sec, date, origin, dest, speed, accessible, max_transfers)
        finally:
            _SPEED.reset(tokens[0])
            _BLOCK.reset(tokens[1])
            _WALK_MODE.reset(tokens[2])
            _EXCLUDE.reset(tokens[3])

    def _query(self, frm, to, profile, now, now_sec, date, origin, dest, speed, accessible, max_transfers):
        stops = [_mapped(s) for s in mkuran.vertices()]
        stops = [s for s in stops if not _inside(s["lat"], s["lon"])]
        boards = spread_groups(_by_street(origin, nearby(origin, stops, WALK_M[profile], 40, _distance, accessible), profile), 8)
        alights = spread_groups(_by_street(dest, nearby(dest, stops, WALK_M[profile], 40, _distance, accessible), profile, "to"), 8)
        dest_ids = {s["id"] for s in alights}

        def departures(stop_id, after):
            return mkuran.departures(stop_id, date, now_sec if after is None else int(after), limit=12)

        def onward(trip_id, stop_id, sec):
            return [_mapped(call, "stop_id") for call in mkuran.trip_onward(trip_id, stop_id, sec)]

        options: list[RouteOption] = []
        walk = self._walk_option(frm, to, origin, dest, profile, now)
        if walk and _option_clear(walk):
            options.append(walk)
        if speed["bike"] > 0:
            bike = self._bike_option(frm, to, origin, dest, profile, now)
            if bike and _option_clear(bike):
                options.append(bike)

        if boards and alights:
            foot = _footpaths(stops, 450, accessible)
            directs = [r for r in direct_rides([s["id"] for s in boards], dest_ids, departures, onward, accessible)
                       if _ride_clear(r)]
            transfers = []
            if max_transfers >= 1:
                transfers = [r for r in transfer_rides([s["id"] for s in boards[:5]], dest_ids, departures, onward,
                                                       foot, accessible)
                             if _ride_clear(r["first"]) and _ride_clear(r["second"])]
            doubles = two_transfer_rides([s["id"] for s in boards], dest_ids, departures, onward, foot, accessible) \
                if max_transfers >= 2 else []
            built = []
            if speed["bike"] > 0:
                built.extend(self._bike_with_transit(
                    frm, to, origin, dest, profile, now, now_sec, stops, dest_ids, directs,
                    departures, onward, accessible))
                if max_transfers >= 1:
                    middle = self._bike_in_the_middle(
                        frm, to, origin, dest, profile, now, now_sec, stops, dest_ids,
                        [s["id"] for s in boards], departures, onward, accessible)
                    if middle:
                        built.append(middle)
            for ride in directs:
                option = self._transit_option(frm, to, origin, dest, profile, now, now_sec, [ride], 0, None)
                if option:
                    built.append(option)
            for ride in transfers[:12]:
                option = self._transit_option(
                    frm, to, origin, dest, profile, now, now_sec,
                    [ride["first"], ride["second"]], ride["walk_m"], ride["first"]["calls"][-1])
                if option:
                    built.append(option)
            for ride in doubles:
                option = self._transit_option(
                    frm, to, origin, dest, profile, now, now_sec,
                    ride["rides"], ride["walk_m"], ride["rides"][0]["calls"][-1])
                if option:
                    built.append(option)
            built.sort(key=lambda o: o.durationMin)
            seen = set()
            for option in built:
                if option.transfers > max_transfers or not _option_clear(option):
                    continue
                key = tuple((leg.mode, leg.line, leg.from_, leg.to) for leg in option.legs)
                if key in seen:
                    continue
                seen.add(key)
                options.append(option)
                if sum(1 for o in options if any(leg.mode not in ("walk", "bike", "veturilo") for leg in o.legs)) >= 4:
                    break

        options.sort(key=lambda o: o.durationMin)
        options = options[:6]
        _tag(options)
        return options

    def _plan(self, frm, to, profile, now, origin, dest, mode, speed, max_transfers) -> list[RouteOption]:
        """Transit options planned by RAPTOR in the router (POST /plan), plus one later query for more departures."""
        date, sec = street_router.service_time(now)
        options = _plan_options(speed, max_transfers, profile)
        raws = street_router.plan(origin, dest, mode, date=date, time=sec, **options)
        departures = [raw["dep_s"] for raw in raws if _counted(raw)]
        if departures and len(raws) < MAX_OPTIONS:
            raws += street_router.plan(origin, dest, mode, date=date, time=int(min(departures)) + 60, **options)
        built = [self._plan_option(raw, frm.label, to.label, origin, dest, date, profile) for raw in raws]
        return _finish(built)

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

    def _walk_option(self, frm, to, origin, dest, profile, now) -> Optional[RouteOption]:
        if _distance(origin, dest) > 5000:
            return None
        street = _street(origin, dest, "walk", profile)
        if street is None or _seconds(street) > 50 * 60:
            return None
        legs = legs_from_router(street, from_name=frm.label, to_name=to.label, points=(origin, dest))
        return _street_tags(_option("walk", "Pieszo", legs, now, _seconds(street)), street, profile)

    def _street_option(self, frm, to, origin, dest, profile, now, travel):
        mode = "bike" if travel == "bike" else "walk"
        street = _street(origin, dest, mode, profile, strict=True)
        if street is None:
            raise ValueError("cycling is disabled by the selected profile or speed")
        legs = legs_from_router(street, from_name=frm.label, to_name=to.label, points=(origin, dest))
        title = {"walk": "Pieszo", "accessible": "Wózek inwalidzki",
                 "stroller": "Wózek dziecięcy", "bike": "Własny rower"}[travel]
        return _street_tags(_option("street-" + travel, title, legs, now, _seconds(street)), street, profile)

    def _bike_option(self, frm, to, origin, dest, profile, now) -> Optional[RouteOption]:
        stations = _stations()
        pair = best_bike_pair(origin, dest, stations, _distance)
        if pair is None:
            return None
        pickup, dropoff = pair
        bridge = _bike_bridge(origin, frm.label, pickup, dropoff, dest, to.label, profile)
        if bridge is None:
            return None
        legs, seconds, ride_seconds = bridge
        if ride_seconds > 45 * 60:
            return None
        return _option("bike", "Veturilo", legs, now, seconds)

    def _bike_with_transit(self, frm, to, origin, dest, profile, now, now_sec, stops, dest_ids, directs,
                           departures, onward, accessible):
        """One 'bike, then a direct ride' and one 'direct ride, then bike', when either exists."""
        stations = _stations()
        if not stations:
            return []
        found = []
        for pair in bike_access_pairs(origin, dest, stations, stops, _distance)[:4]:
            rides = direct_rides([pair["stop"]["id"]], dest_ids, departures, onward, accessible)
            if not rides:
                continue
            ride = rides[0]
            board = ride["calls"][0]
            bridge = _bike_bridge(
                origin, frm.label, pair["pickup"], pair["dropoff"],
                board["stop_id"], board["name"], profile)
            if bridge is None:
                continue
            legs, seconds, _ = bridge
            option = self._transit_option(
                frm, to, origin, dest, profile, now, now_sec, [ride], 0, None,
                lead=(legs, seconds), skip_access=True)
            if option:
                found.append(option)
                break
        far = None
        for ride in directs:
            last = ride["calls"][-1]
            gap = _distance((last["lat"], last["lon"]), dest)
            if gap > 800 and (far is None or gap > far[0]):
                far = (gap, ride)
        if far is not None:
            ride = far[1]
            last = ride["calls"][-1]
            pair = best_bike_pair((last["lat"], last["lon"]), dest, stations, _distance, max_m=800)
            if pair is not None:
                bridge = _bike_bridge(
                    last["stop_id"], last["name"], pair[0], pair[1], dest, to.label, profile)
                if bridge is not None:
                    legs, seconds, _ = bridge
                    option = self._transit_option(
                        frm, to, origin, dest, profile, now, now_sec, [ride], 0, None,
                        egress=(legs, seconds))
                    if option:
                        found.append(option)
        return found

    def _bike_in_the_middle(self, frm, to, origin, dest, profile, now, now_sec, stops, dest_ids, boards,
                            departures, onward, accessible):
        """Veturilo between two public-transport rides."""
        found = bike_between(
            boards, dest_ids, dest, departures, onward, _stations(), stops, _distance, accessible)
        if not found:
            return None
        alight = found["first"]["calls"][-1]
        board = found["second"]["calls"][0]
        bridge = _bike_bridge(
            alight["stop_id"], alight["name"], found["pickup"], found["dropoff"],
            board["stop_id"], board["name"], profile)
        if bridge is None:
            return None
        legs, seconds, _ = bridge
        option = self._transit_option(
            frm, to, origin, dest, profile, now, now_sec,
            [found["first"], found["second"]], 0, None,
            between=(legs, seconds))
        if option:
            lines = [found["first"]["dep"]["line"], found["second"]["dep"]["line"]]
            option.title = f"{lines[0]} + Veturilo + {lines[1]}"
        return option

    def _transit_option(self, frm, to, origin, dest, profile, now, now_sec, rides, between_m, between_stop,
                        lead=None, skip_access=False, egress=None, between=None):
        first = rides[0]["calls"][0]
        last = rides[-1]["calls"][-1]
        lead_legs, lead_s = lead if lead else ([], 0.0)
        if skip_access:
            access_s = 0.0
            access_legs = []
        else:
            access = _street(origin, first["stop_id"], "walk", profile)
            if access is None:
                return None
            access_s = _seconds(access)
            access_legs = legs_from_router(access, from_name=frm.label, to_name=first["name"],
                                           points=(origin, first["stop_id"]))
        if egress is None:
            street = _street(last["stop_id"], dest, "walk", profile)
            if street is None:
                return None
            egress_legs = legs_from_router(street, from_name=last["name"], to_name=to.label,
                                           points=(last["stop_id"], dest))
            egress_s = _seconds(street)
        else:
            egress_legs, egress_s = egress
        if lead_s + access_s + CATCH_SLACK_S > rides[0]["dep"]["sec"] - now_sec:
            return None
        leave = now + timedelta(seconds=max(0, rides[0]["dep"]["sec"] - now_sec - lead_s - access_s))
        legs = list(lead_legs)
        legs.extend(access_legs)
        # Service seconds when the user stands at the next boarding stop (for its waitS).
        ready = (leave - now).total_seconds() + now_sec + lead_s + access_s
        for index, ride in enumerate(rides):
            calls = ride["calls"]
            if index == 1 and between is not None:
                between_legs, between_s = between
                ready = rides[index - 1]["calls"][-1]["arr"] + between_s
                if ride["dep"]["sec"] < rides[index - 1]["calls"][-1]["arr"] + between_s - CATCH_SLACK_S:
                    return None
                legs.extend(between_legs)
            elif index > 0:
                prev = rides[index - 1]["calls"][-1]
                if prev.get("stop_id") != calls[0].get("stop_id"):
                    mid = _street(prev["stop_id"], calls[0]["stop_id"], "walk", profile)
                    if mid is None:
                        return None
                    if ride["dep"]["sec"] < prev["arr"] + _seconds(mid) - CATCH_SLACK_S:
                        return None
                    legs.extend(legs_from_router(mid, from_name=prev["name"], to_name=calls[0]["name"],
                                                    points=(prev["stop_id"], calls[0]["stop_id"])))
                    ready = prev["arr"] + _seconds(mid)
                else:
                    if ride["dep"]["sec"] < prev["arr"] - CATCH_SLACK_S:
                        return None
                    ready = prev["arr"]
            if len(calls) < 2:
                return None
            dep = ride["dep"]
            path, approximate = geometry.leg_path(
                {"mode": dep["mode"], "trip_id": dep["trip_id"],
                 "from": calls[0]["stop_id"], "to": calls[-1]["stop_id"]}, calls=calls)
            path = [tuple(point) for point in path]
            meters = sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))
            seconds = max(0, calls[-1]["arr"] - calls[0]["dep"])
            legs.append(RouteLeg(
                mode=dep["mode"], from_=calls[0]["name"], to=calls[-1]["name"], line=dep["line"],
                durationMin=_minutes(seconds), distanceM=round(meters, 1), path=path,
                fromId=calls[0]["stop_id"], toId=calls[-1]["stop_id"],
                start=tuple(reversed(_pos(calls[0]["stop_id"], (calls[0]["lat"], calls[0]["lon"])))),
                end=tuple(reversed(_pos(calls[-1]["stop_id"], (calls[-1]["lat"], calls[-1]["lon"])))),
                approximatePath=approximate, tripId=dep["trip_id"],
                waitS=round(max(0.0, calls[0]["dep"] - ready), 1),
            ))
        legs.extend(egress_legs)
        title = " + ".join(ride["dep"]["line"] for ride in rides)
        if between is not None:
            parts = title.split(" + ")
            if len(parts) == 2:
                title = f"{parts[0]} + Veturilo + {parts[1]}"
        elif lead or egress:
            title = "Veturilo + " + title
        delay = self._delay(rides[0], now_sec)
        leave = leave + timedelta(seconds=delay)
        door_s = (rides[-1]["calls"][-1]["arr"] + egress_s) - (rides[0]["dep"]["sec"] - access_s - lead_s)
        option = _option("pt-" + "-".join(ride["dep"]["trip_id"] for ride in rides), title, legs, leave, door_s)
        if delay >= 60:
            option.tags.append(f"opóźnienie {max(1, round(delay / 60))} min")
        if any(ride["dep"]["line"] in alerts.alerted_lines() for ride in rides):
            option.tags.append("Zmiana na trasie")
        return option

    def _delay(self, ride: dict, now_sec: int) -> int:
        dep = ride["dep"]
        calls = ride.get("calls") or []
        trip_id = dep.get("trip_id") or ""
        posted = getattr(self, "_trip_delays", {}).get(trip_id) or getattr(self, "_trip_delays", {}).get(trip_id.split(":")[-1]) or 0
        station = 0
        if dep.get("feed") == "pkp" and getattr(self, "_station_delays", {}):
            plk = mkuran.plk_ids()
            for call in calls:
                station = max(station, self._station_delays.get(plk.get(call.get("stop_id"), ""), 0))
        late = 0
        if dep.get("mode") in ("bus", "tram") and calls:
            vehicle = next((v for v in getattr(self, "_vehicles", [])
                            if v.get("line") == dep.get("line")
                            and str(v.get("brigade")) == str(dep.get("brigade"))), None)
            if vehicle is not None:
                whole = mkuran.whole_trip(trip_id, calls[0]["stop_id"], dep["sec"])
                if len(whole) >= 2:
                    late = lateness_s(whole, (vehicle["lat"], vehicle["lon"]), now_sec, _distance)
        return max(late, int(posted), station)


MAX_OPTIONS = 6


def _plan_ready(mode: str) -> bool:
    """True when the router's timetable and the mode's plan are ready (GET /health); else log and say no."""
    health = street_router.health()
    timetable = (health.get("timetable") or {}).get("status")
    plan = (health.get("plan") or {}).get(mode)
    if timetable == "ok" and plan == "ok":
        return True
    log.warning("route engine: /plan not ready for %s (timetable %s, plan %s); using the Python planner",
                mode, timetable, plan)
    return False


def _plan_options(speed, max_transfers, profile) -> dict:
    """The /plan keys from the preferences: speeds, counted legs, no Veturilo when cycling is off."""
    options = {"speeds": _router_speeds(profile), "max_legs": max_transfers + 1}
    if speed["bike"] <= 0:
        options["veturilo_s"] = 0
    if _EXCLUDE.get():
        options["exclude_modes"] = sorted(_EXCLUDE.get())
    return options


def _counted(raw: dict) -> bool:
    """A /plan option with a transit ride or a Veturilo rental (not the street-only trip)."""
    return any(leg["mode"] not in ("walk", "bike") for leg in raw.get("legs") or [])


def _plan_title(legs: list[RouteLeg]) -> str:
    parts = [("Veturilo" if leg.mode == "veturilo" else leg.line or leg.mode) for leg in legs
             if leg.mode not in ("walk", "bike")]
    return " + ".join(parts) or ("Własny rower" if any(leg.mode == "bike" for leg in legs) else "Pieszo")


def _plan_id(legs: list[RouteLeg]) -> str:
    """`pt-<trip id>-...` (POST /api/live/route-delays reads it), else `bike` (Veturilo only) or `walk`."""
    trips = [leg.tripId for leg in legs if leg.tripId]
    if trips:
        return "pt-" + "-".join(trips)
    return "bike" if any(leg.mode == "veturilo" for leg in legs) else "walk"


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


def _by_street(origin, candidates, profile, direction="from"):
    """Rank candidates with one search; egress follows the streets towards the destination.

    When the search works but reaches none of them, fall back to the 8 nearest by straight line
    (a point off the street graph, 404 / 422, cannot walk to any stop, so it gets none)."""
    if not candidates:
        return []
    try:
        reachable = street_router.access(origin, _router_mode("walk", profile), direction, 18 * 60,
                                         speeds=_router_speeds(profile))
    except street_router.RouteError as exc:
        if exc.status not in (404, 422):
            raise
        return []
    times = {stop["id"]: stop["seconds"] for stop in reachable if stop["seconds"] <= 18 * 60}
    ranked = sorted((stop for stop in candidates if stop["id"] in times), key=lambda stop: times[stop["id"]])
    if ranked:
        return ranked
    return sorted(candidates, key=lambda stop: _distance(origin, (stop["lat"], stop["lon"])))[:8]


def _ride_clear(ride) -> bool:
    calls = ride.get("calls") or []
    mids = calls[1:-1] if len(calls) > 2 else []
    return not any(_inside(call.get("lat"), call.get("lon")) for call in mids)


def _option_clear(option: RouteOption) -> bool:
    """False when the option uses an excluded mode (the safety net) or its path enters an excluded area."""
    if any(leg.mode in _EXCLUDE.get() for leg in option.legs):
        return False
    for leg in option.legs:
        for point in leg.path[1:-1]:
            if _inside(point[0], point[1]):
                return False
    return True


def _trip_delays() -> dict:
    try:
        from sources.realtime import delays_by_trip
        return delays_by_trip()
    except Exception as exc:
        log.warning("trip delays skipped: %s", exc)
        return {}


def _station_delays() -> dict:
    try:
        from sources.realtime import delays_by_station
        return delays_by_station()
    except Exception as exc:
        log.warning("station delays skipped: %s", exc)
        return {}


def _live_vehicles() -> list[dict]:
    """Bus and tram positions. Empty when the key is missing or the feed fails."""
    try:
        from sources.um_warszawa import fetch_vehicles, fresh
        rows = []
        for kind in ("bus", "tram"):
            rows.extend(fresh(fetch_vehicles(kind)))
        return rows
    except Exception as exc:
        log.warning("live positions skipped: %s", exc)
        return []


_FOOT_CACHE: dict = {}


def _footpaths(stops: list[dict], max_m: float, step_free: bool = False) -> dict[str, list]:
    """Stop id -> places you can change: nearby posts, the same station, transfers.txt, pathways."""
    from scipy.spatial import cKDTree

    from config import to_xy
    import numpy as np

    if len(stops) < 2:
        return {}
    key = (stops[0]["id"], stops[-1]["id"], len(stops), max_m, step_free)
    cached = _FOOT_CACHE.get(key)
    if cached is not None:
        return cached
    lat = np.array([s["lat"] for s in stops])
    lon = np.array([s["lon"] for s in stops])
    x, y = to_xy(lat, lon)
    pairs = cKDTree(np.column_stack((x, y))).query_pairs(max_m)
    out: dict[str, list] = {}
    for i, j in pairs:
        meters = _distance((stops[i]["lat"], stops[i]["lon"]), (stops[j]["lat"], stops[j]["lon"]))
        out.setdefault(stops[i]["id"], []).append((stops[j]["id"], meters, 0))
        out.setdefault(stops[j]["id"], []).append((stops[i]["id"], meters, 0))
    by_group: dict[str, list] = {}
    for stop in stops:
        by_group.setdefault(stop.get("group") or stop["id"], []).append(stop)
    for members in by_group.values():
        if len(members) < 2:
            continue
        for a in members:
            near = []
            for b in members:
                if a["id"] == b["id"]:
                    continue
                meters = _distance((a["lat"], a["lon"]), (b["lat"], b["lon"]))
                if meters <= 350:
                    near.append((b["id"], meters, 60))
            near.sort(key=lambda item: item[1])
            out.setdefault(a["id"], []).extend(near[:3])
    valid_ids = {stop["id"] for stop in stops}

    def add_link(a, b, meters, seconds):
        try:
            a, b = mkuran.canonical(a), mkuran.canonical(b)
        except KeyError:
            return  # feeds can reference a child stop outside the imported area
        if a in valid_ids and b in valid_ids:
            out.setdefault(a, []).append((b, meters, seconds))

    try:
        for a, b, sec in mkuran.transfer_links():
            add_link(a, b, 80.0, sec)
        for a, b, meters, sec in mkuran.pathway_links(step_free):
            add_link(a, b, meters or 40.0, sec)
    except (OSError, KeyError) as exc:
        log.warning("transfer links skipped: %s", exc)
    for stop_id in out:
        out[stop_id].sort(key=lambda item: item[1])
    _FOOT_CACHE[key] = out
    return out


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


def _bike_bridge(a_point, a_label, pickup, dropoff, b_point, b_label, profile):
    """Walk to a bike, ride, walk on. ``(legs, seconds, ride_seconds)`` or None."""
    walk_to = _street(a_point, pickup["id"], "walk", profile)
    ride = _street(pickup["id"], dropoff["id"], "bike", profile)
    walk_from = _street(dropoff["id"], b_point, "walk", profile)
    if not walk_to or not ride or not walk_from:
        return None
    legs = [
        *legs_from_router(walk_to, from_name=a_label, to_name=pickup["name"], points=(a_point, pickup["id"])),
        *legs_from_router(ride, from_name=pickup["name"], to_name=dropoff["name"], rented=True,
                          points=(pickup["id"], dropoff["id"])),
        *legs_from_router(walk_from, from_name=dropoff["name"], to_name=b_label, points=(dropoff["id"], b_point)),
    ]
    return legs, _seconds(walk_to) + _seconds(ride) + _seconds(walk_from), _seconds(ride)


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


def _stations() -> list[dict]:
    try:
        types = {}
        for kind in nextbike.vehicle_types():
            types[kind["vehicle_type_id"]] = kind.get("propulsion_type")
        live = {row["station_id"]: row for row in nextbike.status()}
        out = []
        for station in nextbike.stations(live=False):
            row = live.get(station["station_id"], {})
            counts = row.get("types") or []
            human = sum(item.get("count", 0) for item in counts
                        if types.get(item.get("vehicle_type_id")) != "electric_assist")
            electric_n = sum(item.get("count", 0) for item in counts
                             if types.get(item.get("vehicle_type_id")) == "electric_assist")
            docks = row.get("docks")
            if docks is None:
                docks = 1 if station.get("virtual") else 0
            if station.get("virtual") and row.get("returning", True):
                docks = max(int(docks or 0), 1)
            station_id = station["id"]
            lat, lon = _pos(station_id, (station["lat"], station["lon"]))
            out.append({
                "id": station_id,
                "name": station["name"],
                "lat": lat,
                "lon": lon,
                "bikes": row.get("bikes") or 0,
                "docks": docks,
                "electric": electric_n > 0 and human == 0,
                "renting": row.get("renting", True),
                "returning": row.get("returning", True),
            })
        return [s for s in out if s["renting"] or s["returning"]]
    except Exception as exc:
        log.warning("Veturilo stations unavailable: %s", exc)
        return []


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
