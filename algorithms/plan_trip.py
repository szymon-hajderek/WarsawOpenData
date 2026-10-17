"""Pick direct rides and one-transfer rides from timetable callbacks. No files, no HTTP."""
from __future__ import annotations


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
        if pickup.get("bikes", 0) <= 0:
            continue
        to_pickup = distance(origin, (pickup["lat"], pickup["lon"]))
        if to_pickup > max_m:
            continue
        for dropoff in stations:
            if pickup["id"] == dropoff["id"] or (dropoff.get("docks") or 0) <= 0:
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
