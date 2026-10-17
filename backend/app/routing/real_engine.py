"""Routes from the parsed GTFS timetable, the OSM street graph and live Veturilo status.

One direct public-transport ride, one transfer, a Veturilo ride and a walk. Street geometry
comes from OSM for the options that are returned; the search itself ranks with straight-line
time so it does not run Dijkstra for every stop.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any, Optional

from config import REPO, haversine_m

sys.path.insert(0, str(REPO / "algorithms"))
from fares import cheapest_fare, veturilo_pln  # noqa: E402
from plan_trip import best_bike_pair, direct_rides, nearby, transfer_rides  # noqa: E402

from sources import alerts, mkuran, nextbike, osm

from ..models import Place, Profile, RouteLeg, RouteOption
from .engine import RouteEngine
from .geo import format_time, round_half_up

OSM_SPEED = {"walk": 1.3, "bike": 4.2}
PROFILE_SPEED = {
    "standard": {"walk": 1.3, "bike": 4.2},
    "slow": {"walk": 0.9, "bike": 3.0},
    "accessible": {"walk": 1.0, "bike": 0.0},
}
KCAL_PER_KM = {"walk": 55, "bike": 32}
WALK_M = {"standard": 900, "slow": 700, "accessible": 600}
CATCH_SLACK_S = 20


def _distance(a, b) -> float:
    return haversine_m(a[0], a[1], b[0], b[1])


def _minutes(seconds: float) -> int:
    if seconds <= 0:
        return 0
    return max(1, round_half_up(seconds / 60))


class RealRouteEngine(RouteEngine):
    def update_state(self, update: dict[str, Any]) -> None:
        return None

    def query_routes(self, frm: Place, to: Place, profile: Profile) -> list[RouteOption]:
        now = datetime.now()
        now_sec = now.hour * 3600 + now.minute * 60 + now.second
        date = now.strftime("%Y%m%d")
        accessible = profile == "accessible"
        origin = tuple(frm.position)
        dest = tuple(to.position)
        speed = PROFILE_SPEED[profile]

        stops = mkuran.vertices()
        boards = nearby(origin, stops, WALK_M[profile], 8, _distance, accessible)
        alights = nearby(dest, stops, WALK_M[profile], 8, _distance, accessible)
        dest_ids = {s["id"] for s in alights}

        def departures(stop_id, after):
            return mkuran.departures(stop_id, date, now_sec if after is None else int(after), limit=12)

        def onward(trip_id, stop_id, sec):
            return mkuran.trip_onward(trip_id, stop_id, sec)

        options: list[RouteOption] = []
        walk = self._walk_option(frm, to, origin, dest, profile, now)
        if walk:
            options.append(walk)
        if speed["bike"] > 0:
            bike = self._bike_option(frm, to, origin, dest, profile, now)
            if bike:
                options.append(bike)

        if boards and alights:
            foot = _footpaths(stops, 450)
            directs = direct_rides([s["id"] for s in boards], dest_ids, departures, onward, accessible)
            transfers = transfer_rides([s["id"] for s in boards[:5]], dest_ids, departures, onward,
                                       foot, accessible)
            built = []
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
            built.sort(key=lambda o: o.durationMin)
            seen = set()
            for option in built:
                key = tuple((leg.mode, leg.line, leg.from_, leg.to) for leg in option.legs)
                if key in seen:
                    continue
                seen.add(key)
                options.append(option)
                if sum(1 for o in options if any(leg.mode not in ("walk", "bike") for leg in o.legs)) >= 4:
                    break

        options.sort(key=lambda o: o.durationMin)
        options = options[:6]
        _tag(options)
        return options

    def _walk_option(self, frm, to, origin, dest, profile, now) -> Optional[RouteOption]:
        if _distance(origin, dest) > 5000:
            return None
        street = _street(origin, dest, "walk", profile)
        if street is None or street["seconds"] > 50 * 60:
            return None
        leg = _leg("walk", frm.label, to.label, None, street)
        return _option("walk", "Pieszo", [leg], now, 0)

    def _bike_option(self, frm, to, origin, dest, profile, now) -> Optional[RouteOption]:
        stations = _stations()
        pair = best_bike_pair(origin, dest, stations, _distance)
        if pair is None:
            return None
        pickup, dropoff = pair
        walk_to = _street(origin, (pickup["lat"], pickup["lon"]), "walk", profile)
        ride = _street((pickup["lat"], pickup["lon"]), (dropoff["lat"], dropoff["lon"]), "bike", profile)
        walk_from = _street((dropoff["lat"], dropoff["lon"]), dest, "walk", profile)
        if not walk_to or not ride or not walk_from or ride["seconds"] > 45 * 60:
            return None
        legs = [
            _leg("walk", frm.label, pickup["name"], None, walk_to),
            _leg("bike", pickup["name"], dropoff["name"], None, ride),
            _leg("walk", dropoff["name"], to.label, None, walk_from),
        ]
        return _option("bike", "Veturilo", legs, now, veturilo_pln(ride["seconds"] / 60, pickup["electric"]))

    def _transit_option(self, frm, to, origin, dest, profile, now, now_sec, rides, between_m, between_stop):
        first = rides[0]["calls"][0]
        last = rides[-1]["calls"][-1]
        access = _street(origin, (first["lat"], first["lon"]), "walk", profile)
        egress = _street((last["lat"], last["lon"]), dest, "walk", profile)
        if access is None or egress is None:
            return None
        if access["seconds"] + CATCH_SLACK_S > rides[0]["dep"]["sec"] - now_sec:
            return None
        leave = now + timedelta(seconds=max(0, rides[0]["dep"]["sec"] - now_sec - access["seconds"]))
        legs = [_leg("walk", frm.label, first["name"], None, access)]
        zones = set()
        route_ids = set()
        for index, ride in enumerate(rides):
            calls = ride["calls"]
            if index > 0 and between_m > 0 and between_stop is not None:
                mid = _street((between_stop["lat"], between_stop["lon"]),
                              (calls[0]["lat"], calls[0]["lon"]), "walk", profile)
                if mid is None:
                    return None
                if ride["dep"]["sec"] < rides[index - 1]["calls"][-1]["arr"] + mid["seconds"] - CATCH_SLACK_S:
                    return None
                legs.append(_leg("walk", between_stop["name"], calls[0]["name"], None, mid))
            path = _ride_path(ride["dep"]["trip_id"], calls)
            meters = sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))
            seconds = max(0, calls[-1]["arr"] - calls[0]["dep"])
            dep = ride["dep"]
            legs.append(RouteLeg(
                mode=dep["mode"], from_=calls[0]["name"], to=calls[-1]["name"], line=dep["line"],
                durationMin=_minutes(seconds), distanceM=round(meters, 1), path=path,
            ))
            zones.update(c["zone"] for c in calls if c.get("zone"))
            route_ids.add(dep["route_id"].split(":", 1)[-1])
        legs.append(_leg("walk", last["name"], to.label, None, egress))
        ticket_s = rides[-1]["calls"][-1]["arr"] - rides[0]["dep"]["sec"]
        price = cheapest_fare(mkuran.fare_table(), zones, ticket_s, route_ids)
        if price is None:
            feeds = {ride["dep"].get("feed") for ride in rides}
            price = 7.0 if feeds - {"ztm"} else 4.4
        title = " + ".join(ride["dep"]["line"] for ride in rides)
        door_s = (rides[-1]["calls"][-1]["arr"] + egress["seconds"]) - (rides[0]["dep"]["sec"] - access["seconds"])
        option = _option("pt-" + "-".join(ride["dep"]["trip_id"] for ride in rides), title, legs, leave,
                         price, door_s)
        if any(ride["dep"]["line"] in alerts.alerted_lines() for ride in rides):
            option.tags.append("Zmiana na trasie")
        return option


def _footpaths(stops: list[dict], max_m: float) -> dict[str, list[tuple[str, float]]]:
    """Stop id -> other stops within `max_m` in a straight line, closest first. Used only to change vehicles."""
    from scipy.spatial import cKDTree

    from config import to_xy
    import numpy as np

    if len(stops) < 2:
        return {}
    lat = np.array([s["lat"] for s in stops])
    lon = np.array([s["lon"] for s in stops])
    x, y = to_xy(lat, lon)
    pairs = cKDTree(np.column_stack((x, y))).query_pairs(max_m)
    out: dict[str, list[tuple[str, float]]] = {}
    for i, j in pairs:
        meters = _distance((stops[i]["lat"], stops[i]["lon"]), (stops[j]["lat"], stops[j]["lon"]))
        out.setdefault(stops[i]["id"], []).append((stops[j]["id"], meters))
        out.setdefault(stops[j]["id"], []).append((stops[i]["id"], meters))
    for key in out:
        out[key].sort(key=lambda item: item[1])
    return out


def _street(a, b, mode: str, profile: Profile):
    speed = PROFILE_SPEED[profile][mode]
    if speed <= 0:
        return None
    try:
        raw = osm.route(a[0], a[1], b[0], b[1], mode)
        scale = OSM_SPEED[mode] / speed
        return {"seconds": raw["seconds"] * scale, "length_m": raw["length_m"], "geometry": raw["geometry"]}
    except (ValueError, OSError, FileNotFoundError):
        meters = _distance(a, b) * 1.25
        return {"seconds": meters / speed, "length_m": meters, "geometry": [list(a), list(b)]}


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
            out.append({
                "id": station["station_id"],
                "name": station["name"],
                "lat": station["lat"],
                "lon": station["lon"],
                "bikes": row.get("bikes") or 0,
                "docks": row.get("docks") if row.get("docks") is not None else 1,
                "electric": electric_n > 0 and human == 0,
                "renting": row.get("renting", True),
            })
        return [s for s in out if s["renting"]]
    except Exception:
        return []


def _ride_path(trip_id: str, calls: list[dict]) -> list[list[float]]:
    try:
        shape = mkuran.shape_slice(mkuran.trip_shape_id(trip_id), calls[0]["shape_dist"], calls[-1]["shape_dist"])
    except (KeyError, OSError, ValueError):
        shape = []
    if len(shape) >= 2:
        return shape
    return [[c["lat"], c["lon"]] for c in calls]


def _leg(mode, frm, to, line, street) -> RouteLeg:
    return RouteLeg(mode=mode, from_=frm, to=to, line=line, durationMin=_minutes(street["seconds"]),
                    distanceM=round(street["length_m"], 1), path=street["geometry"])


def _option(option_id, title, legs, leave, cost, door_s: float | None = None) -> RouteOption:
    calories = 0
    for leg in legs:
        rate = KCAL_PER_KM.get(leg.mode)
        if rate:
            calories += leg.distanceM / 1000 * rate
    non_walk = sum(1 for leg in legs if leg.mode != "walk")
    duration = _minutes(door_s) if door_s is not None else sum(leg.durationMin for leg in legs)
    return RouteOption(
        id=option_id, title=title, legs=legs,
        departure=format_time(leave), arrival=format_time(leave + timedelta(minutes=duration)),
        durationMin=duration, distanceM=round(sum(leg.distanceM for leg in legs), 1),
        calories=round_half_up(calories), transfers=max(0, non_walk - 1), costPln=round(cost, 2), tags=[],
    )


def _tag(options: list[RouteOption]) -> None:
    if not options:
        return
    options[0].tags.append("Najszybsza")
    best = min(o.costPln for o in options)
    cheapest = [o for o in options if o.costPln == best]
    if len(cheapest) == 1 and len(options) > 1:
        cheapest[0].tags.append("Najtańsza")
    active = max(options, key=lambda o: o.calories)
    if active.calories > 0 and len(active.tags) < 2:
        active.tags.append("Najaktywniejsza")
