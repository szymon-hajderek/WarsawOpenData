"""Routes from the parsed GTFS timetable, the OSM street graph and live Veturilo status.

A walk, a Veturilo ride, Veturilo before or after one ride, Veturilo between two rides, a direct
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
from fares import brackets_for, cheapest_fare, open_fare, veturilo_from_brackets, veturilo_pln  # noqa: E402
from lateness import lateness_s  # noqa: E402
from plan_trip import (  # noqa: E402
    as_warsaw, best_bike_pair, bike_access_pairs, bike_between, direct_rides, nearby, service_moment,
    spread_groups, transfer_rides, two_transfer_rides, warsaw_offset,
)

log = logging.getLogger("uvicorn.error")

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
WALK_M = {"standard": 900, "slow": 700, "accessible": 600}
CATCH_SLACK_S = 20
_SPEED = contextvars.ContextVar("route_speed", default=None)
_BLOCK = contextvars.ContextVar("route_block", default=None)


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
        self._vehicles = _live_vehicles()
        self._trip_delays = _trip_delays()
        self._station_delays = _station_delays()
        speed, accessible, max_transfers, block = _limits(profile, search)
        origin = tuple(frm.position)
        dest = tuple(to.position)
        tokens = (_SPEED.set(speed), _BLOCK.set(block))
        try:
            return self._query(frm, to, profile, now, now_sec, date, origin, dest, speed, accessible, max_transfers)
        finally:
            _SPEED.reset(tokens[0])
            _BLOCK.reset(tokens[1])

    def _query(self, frm, to, profile, now, now_sec, date, origin, dest, speed, accessible, max_transfers):
        stops = [s for s in mkuran.vertices() if not _inside(s["lat"], s["lon"])]
        boards = spread_groups(_by_street(origin, nearby(origin, stops, WALK_M[profile], 40, _distance, accessible), profile), 8)
        alights = spread_groups(_by_street(dest, nearby(dest, stops, WALK_M[profile], 40, _distance, accessible), profile), 8)
        dest_ids = {s["id"] for s in alights}

        def departures(stop_id, after):
            return mkuran.departures(stop_id, date, now_sec if after is None else int(after), limit=12)

        def onward(trip_id, stop_id, sec):
            return mkuran.trip_onward(trip_id, stop_id, sec)

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
            _leg("veturilo", pickup["name"], dropoff["name"], None, ride),
            _leg("walk", dropoff["name"], to.label, None, walk_from),
        ]
        return _option("bike", "Veturilo", legs, now)

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
                (board["lat"], board["lon"]), board["name"], profile)
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
                    (last["lat"], last["lon"]), last["name"], pair[0], pair[1], dest, to.label, profile)
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
            (alight["lat"], alight["lon"]), alight["name"], found["pickup"], found["dropoff"],
            (board["lat"], board["lon"]), board["name"], profile)
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
            access_leg = None
        else:
            access = _street(origin, (first["lat"], first["lon"]), "walk", profile)
            if access is None:
                return None
            access_s = access["seconds"]
            access_leg = _leg("walk", frm.label, first["name"], None, access)
        if egress is None:
            street = _street((last["lat"], last["lon"]), dest, "walk", profile)
            if street is None:
                return None
            egress_legs, egress_s = [_leg("walk", last["name"], to.label, None, street)], street["seconds"]
        else:
            egress_legs, egress_s = egress
        if lead_s + access_s + CATCH_SLACK_S > rides[0]["dep"]["sec"] - now_sec:
            return None
        leave = now + timedelta(seconds=max(0, rides[0]["dep"]["sec"] - now_sec - lead_s - access_s))
        legs = list(lead_legs)
        if access_leg is not None:
            legs.append(access_leg)
        for index, ride in enumerate(rides):
            calls = ride["calls"]
            if index == 1 and between is not None:
                between_legs, between_s = between
                if ride["dep"]["sec"] < rides[index - 1]["calls"][-1]["arr"] + between_s - CATCH_SLACK_S:
                    return None
                legs.extend(between_legs)
            elif index > 0:
                prev = rides[index - 1]["calls"][-1]
                if prev.get("stop_id") != calls[0].get("stop_id"):
                    mid = _street((prev["lat"], prev["lon"]), (calls[0]["lat"], calls[0]["lon"]), "walk", profile)
                    if mid is None:
                        return None
                    if ride["dep"]["sec"] < prev["arr"] + mid["seconds"] - CATCH_SLACK_S:
                        return None
                    legs.append(_leg("walk", prev["name"], calls[0]["name"], None, mid))
                elif ride["dep"]["sec"] < prev["arr"] - CATCH_SLACK_S:
                    return None
            path = _ride_path(ride["dep"]["trip_id"], calls)
            meters = sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))
            seconds = max(0, calls[-1]["arr"] - calls[0]["dep"])
            dep = ride["dep"]
            legs.append(RouteLeg(
                mode=dep["mode"], from_=calls[0]["name"], to=calls[-1]["name"], line=dep["line"],
                durationMin=_minutes(seconds), distanceM=round(meters, 1), path=path,
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
    return speed, accessible, max_transfers, block


def _inside(lat, lon) -> bool:
    spec = _BLOCK.get()
    if not spec or lat is None or lon is None:
        return False
    return blocked(float(lat), float(lon), spec[0], spec[1], _distance)


def _by_street(origin, candidates, profile):
    """Re-rank the nearest stops by OSM walk time. The straight-line list is only the candidate pool."""
    ranked = []
    for stop in candidates[:12]:
        street = _street(origin, (stop["lat"], stop["lon"]), "walk", profile)
        if street is None or street["seconds"] > 18 * 60:
            continue
        ranked.append((street["seconds"], stop))
    ranked.sort(key=lambda item: item[0])
    return [stop for _, stop in ranked] or list(candidates[:8])


def _ride_clear(ride) -> bool:
    calls = ride.get("calls") or []
    mids = calls[1:-1] if len(calls) > 2 else []
    return not any(_inside(call.get("lat"), call.get("lon")) for call in mids)


def _option_clear(option: RouteOption) -> bool:
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
    try:
        for a, b, sec in mkuran.transfer_links():
            out.setdefault(a, []).append((b, 80.0, sec))
        for a, b, meters, sec in mkuran.pathway_links(step_free):
            out.setdefault(a, []).append((b, meters or 40.0, sec))
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


def _ticket(rides, zones, ticket_s, route_ids) -> float:
    """ZTM table, WKD fare file, SKM as a ZTM ticket, and 7 zł where KM has no fare file."""
    feeds = {ride["dep"].get("feed") or "ztm" for ride in rides}
    if feeds == {"ztm"}:
        price = cheapest_fare(mkuran.fare_table(), zones, ticket_s, route_ids)
        return 4.4 if price is None else price
    total = 0.0
    try:
        routes = mkuran.routes()
    except (OSError, KeyError):
        routes = {}
    for feed in feeds:
        ids = set()
        agencies = set()
        for ride in rides:
            if (ride["dep"].get("feed") or "ztm") != feed:
                continue
            rid = ride["dep"].get("route_id") or ""
            ids.add(rid.split(":", 1)[-1])
            agencies.add(routes.get(rid, {}).get("agency"))
        if feed == "ztm" or (feed == "pkp" and agencies and agencies <= {"SKM", "SKMT"}):
            part = cheapest_fare(mkuran.fare_table(), zones, ticket_s, ids or route_ids)
            total += 4.4 if part is None else part
        elif feed == "wkd":
            part = open_fare(mkuran.fare_table_for("wkd"), int(ticket_s))
            total += 4.1 if part is None else part
        else:
            total += 7.0
    return total


def _bike_price(minutes: float, electric: bool) -> float:
    try:
        steps = brackets_for(nextbike.pricing_plans(), electric)
    except Exception as exc:
        log.warning("Veturilo pricing plans unavailable: %s", exc)
        steps = None
    if steps:
        return veturilo_from_brackets(minutes, steps)
    return veturilo_pln(minutes, electric)


def _bike_bridge(a_point, a_label, pickup, dropoff, b_point, b_label, profile):
    """Walk to a bike, ride, walk on. ``(legs, seconds, ride_seconds)`` or None."""
    walk_to = _street(a_point, (pickup["lat"], pickup["lon"]), "walk", profile)
    ride = _street((pickup["lat"], pickup["lon"]), (dropoff["lat"], dropoff["lon"]), "bike", profile)
    walk_from = _street((dropoff["lat"], dropoff["lon"]), b_point, "walk", profile)
    if not walk_to or not ride or not walk_from:
        return None
    legs = [
        _leg("walk", a_label, pickup["name"], None, walk_to),
        _leg("veturilo", pickup["name"], dropoff["name"], None, ride),
        _leg("walk", dropoff["name"], b_label, None, walk_from),
    ]
    return legs, walk_to["seconds"] + ride["seconds"] + walk_from["seconds"], ride["seconds"]


def _street(a, b, mode: str, profile: Profile):
    table = _SPEED.get() or PROFILE_SPEED[profile]
    speed = table[mode]
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
            docks = row.get("docks")
            if docks is None:
                docks = 1 if station.get("virtual") else 0
            if station.get("virtual") and row.get("returning", True):
                docks = max(int(docks or 0), 1)
            out.append({
                "id": station["station_id"],
                "name": station["name"],
                "lat": station["lat"],
                "lon": station["lon"],
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
