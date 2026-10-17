"""Pick direct rides and one-transfer rides from timetable callbacks. No files, no HTTP."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def nearby(origin: tuple[float, float], stops: list[dict], max_m: float, limit: int,
           distance, accessible: bool) -> list[dict]:
    """Closest stops within `max_m`. A stop with wheelchair '2' is skipped for an accessible profile."""
    found = []
    for stop in stops:
        if accessible and stop.get("wheelchair") == "2":
            continue
        meters = distance(origin, (stop["lat"], stop["lon"]))
        if meters <= max_m:
            found.append((meters, stop))
    found.sort(key=lambda item: item[0])
    return [stop for _, stop in found[:limit]]


def spread_groups(stops: list[dict], limit: int) -> list[dict]:
    """One stop per group, closest first. `stops` must already be nearest-first."""
    seen = set()
    out = []
    for stop in stops:
        group = stop.get("group") or stop["id"]
        if group in seen:
            continue
        seen.add(group)
        out.append(stop)
        if len(out) >= limit:
            break
    return out


def _last_sunday(year: int, month: int) -> int:
    if month == 12:
        last = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)
    return last.day - (last.weekday() - 6) % 7


def warsaw_offset(moment: datetime) -> timedelta:
    """Poland civil offset: UTC+2 from the last Sunday of March 01:00 UTC, else UTC+1."""
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    start = datetime(utc.year, 3, _last_sunday(utc.year, 3), 1, tzinfo=timezone.utc)
    end = datetime(utc.year, 10, _last_sunday(utc.year, 10), 1, tzinfo=timezone.utc)
    return timedelta(hours=2) if start <= utc < end else timedelta(hours=1)


def as_warsaw(now: datetime) -> datetime:
    """Naive Europe/Warsaw wall time. A naive input is already treated as Warsaw."""
    if now.tzinfo is None:
        return now
    utc = now.astimezone(timezone.utc)
    return (utc + warsaw_offset(utc)).replace(tzinfo=None)


def service_moment(now: datetime, cutoff_hour: int = 4) -> tuple[str, int]:
    """GTFS service date and seconds from that midnight.

    Before `cutoff_hour` the trip still belongs to yesterday, and the clock is
    written as 24:00+ so it matches GTFS times such as 25:10:00. Aware datetimes
    are converted to Europe/Warsaw first.
    """
    now = as_warsaw(now)
    sec = now.hour * 3600 + now.minute * 60 + now.second
    day = now.date()
    if sec < cutoff_hour * 3600:
        day -= timedelta(days=1)
        sec += 24 * 3600
    return day.strftime("%Y%m%d"), sec


def can_return(station: dict) -> bool:
    """A drop-off needs a free dock and a station that is accepting bikes."""
    if station.get("returning") is False:
        return False
    return (station.get("docks") or 0) > 0


def direct_rides(boards: list[str], dest_ids: set[str], departures, onward,
                 accessible: bool, per_board: int = 12) -> list[dict]:
    """Rides that board at `boards` and alight at one of `dest_ids` without a transfer."""
    found = []
    for stop_id in boards:
        for dep in departures(stop_id, None)[:per_board]:
            if accessible and dep.get("wheelchair") == "2":
                continue
            calls = onward(dep["trip_id"], stop_id, dep["sec"])
            for index, call in enumerate(calls[1:], start=1):
                if accessible and call.get("wheelchair") == "2":
                    continue
                if call["stop_id"] in dest_ids:
                    found.append({"dep": dep, "calls": calls[:index + 1]})
                    break
    return found


def transfer_rides(boards: list[str], dest_ids: set[str], departures, onward, foot: dict,
                   accessible: bool, per_board: int = 5, alights: int = 3) -> list[dict]:
    """One transfer. `foot` maps a stop id to nearby stops `(other_id, meters)`, closest first."""
    found = []
    for stop_id in boards:
        for dep in departures(stop_id, None)[:per_board]:
            if accessible and dep.get("wheelchair") == "2":
                continue
            calls = onward(dep["trip_id"], stop_id, dep["sec"])
            picks = []
            for index, call in enumerate(calls[1:], start=1):
                if call["arr"] - dep["sec"] > 40 * 60:
                    break
                if index == 1 and len(calls) > 3:
                    continue
                if accessible and call.get("wheelchair") == "2":
                    continue
                picks.append((index, call))
            if len(picks) > alights:
                step = len(picks) / alights
                picks = [picks[int(k * step)] for k in range(alights)]
            for index, call in picks:
                neighbors = [(call["stop_id"], 0.0)] + list(foot.get(call["stop_id"], ()))[:3]
                for other_id, meters in neighbors:
                    for dep2 in departures(other_id, call["arr"])[:4]:
                        if dep2["trip_id"] == dep["trip_id"]:
                            continue
                        if dep.get("line") and dep.get("line") == dep2.get("line"):
                            continue
                        if dep2["sec"] < call["arr"] or dep2["sec"] - call["arr"] > 20 * 60:
                            continue
                        if accessible and dep2.get("wheelchair") == "2":
                            continue
                        calls2 = onward(dep2["trip_id"], other_id, dep2["sec"])
                        for index2, call2 in enumerate(calls2[1:], start=1):
                            if accessible and call2.get("wheelchair") == "2":
                                continue
                            if call2["stop_id"] in dest_ids:
                                found.append({
                                    "first": {"dep": dep, "calls": calls[:index + 1]},
                                    "second": {"dep": dep2, "calls": calls2[:index2 + 1]},
                                    "walk_m": meters,
                                })
                                break
    return found


def best_bike_pair(origin, dest, stations: list[dict], distance, max_m: float = 900):
    """Pickup with a bike and drop-off with a free dock, the pair with the shortest three legs."""
    best = None
    for pickup in stations:
        if pickup.get("bikes", 0) <= 0 or pickup.get("renting") is False:
            continue
        to_pickup = distance(origin, (pickup["lat"], pickup["lon"]))
        if to_pickup > max_m:
            continue
        for dropoff in stations:
            if pickup["id"] == dropoff["id"] or not can_return(dropoff):
                continue
            from_dropoff = distance(dest, (dropoff["lat"], dropoff["lon"]))
            if from_dropoff > max_m:
                continue
            ride = distance((pickup["lat"], pickup["lon"]), (dropoff["lat"], dropoff["lon"]))
            score = to_pickup + ride + from_dropoff
            if best is None or score < best[0]:
                best = (score, pickup, dropoff)
    if best is None:
        return None
    return best[1], best[2]


def bike_access_pairs(origin, dest, stations: list[dict], stops: list[dict], distance,
                      max_m: float = 900, stop_m: float = 400, limit: int = 4) -> list[dict]:
    """Pickup near the origin, drop-off nearer the destination beside a transit stop.

    Each item is ``{"pickup", "dropoff", "stop"}``, shortest three-leg score first.
    """
    trip = distance(origin, dest)
    if trip < 1200:
        return []
    pickups = []
    for station in stations:
        if station.get("bikes", 0) <= 0 or station.get("renting") is False:
            continue
        walk = distance(origin, (station["lat"], station["lon"]))
        if walk <= max_m:
            pickups.append((walk, station))
    pickups.sort(key=lambda item: item[0])
    pickups = pickups[:3]

    dropoffs = []
    for station in stations:
        if not can_return(station):
            continue
        left = distance((station["lat"], station["lon"]), dest)
        if 400 < left < trip - 400:
            dropoffs.append((left, station))
    dropoffs.sort(key=lambda item: item[0])
    dropoffs = dropoffs[:25]

    found = []
    for walk, pickup in pickups:
        for _, drop in dropoffs:
            if drop["id"] == pickup["id"]:
                continue
            ride = distance((pickup["lat"], pickup["lon"]), (drop["lat"], drop["lon"]))
            if ride < 400:
                continue
            near = None
            near_m = None
            for stop in stops:
                gap = distance((drop["lat"], drop["lon"]), (stop["lat"], stop["lon"]))
                if gap <= stop_m and (near_m is None or gap < near_m):
                    near, near_m = stop, gap
            if near is None:
                continue
            left = distance((drop["lat"], drop["lon"]), dest)
            found.append((walk + ride + near_m + left, pickup, drop, near))
    found.sort(key=lambda item: item[0])
    out = []
    seen = set()
    for _, pickup, drop, stop in found:
        key = (pickup["id"], stop["id"])
        if key in seen:
            continue
        seen.add(key)
        out.append({"pickup": pickup, "dropoff": drop, "stop": stop})
        if len(out) >= limit:
            break
    return out
