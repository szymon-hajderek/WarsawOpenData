"""Which live vehicle will run each ride of a suggested route? Pure functions, no I/O.

A transit route option id is "pt-" + "-".join(trip ids) (backend/app/routing/real_engine.py). Trip ids have a feed
prefix and may contain "-" themselves (ztm:2026-10-18:504:NdS:1:0519), so the id is split only where "-" is followed
by a feed prefix. A trip's line + brigade (GTFS route_short_name + block_short_name) is the same pair as Lines +
Brigade in the live feed, which points at one vehicle.
"""
import re

FEEDS = ("ztm", "wkd", "pkp")
LIVE_MODES = ("bus", "tram")
_SPLIT = re.compile(r"-(?=(?:%s):)" % "|".join(FEEDS))


def trip_ids_from_option(option_id: str) -> list[str]:
    """Trip ids of a transit option id, in ride order. [] for other ids (walk, bike, multi-N)."""
    if not option_id.startswith("pt-"):
        return []
    parts = _SPLIT.split(option_id[3:])
    return parts if all(p.split(":", 1)[0] in FEEDS for p in parts) else []


def leg_vehicles(trip_ids: list[str], lines: list[str], trips: dict, vehicles: dict) -> list[dict]:
    """For each ride: {"transitIndex", "line", "trip_id", "vehicle_id", "reason"}.

    `trips`: trip id -> {"line", "brigade", "mode"} (GTFS). `vehicles`: (line, brigade) -> live vehicle id.
    `lines`: line of each transit leg of the option, in order; a ride whose line does not match is skipped.
    reason: None (vehicle found), "not_live" (not bus / tram, or unknown trip), "no_vehicle".
    """
    out = []
    for i, trip_id in enumerate(trip_ids):
        trip = trips.get(trip_id)
        line = lines[i] if i < len(lines) else None
        if trip is not None and line is not None and trip["line"] != line:
            continue
        row = {"transitIndex": i, "line": line or (trip or {}).get("line"), "trip_id": trip_id, "vehicle_id": None,
               "reason": None}
        if trip is None or trip["mode"] not in LIVE_MODES:
            row["reason"] = "not_live"
        else:
            row["vehicle_id"] = vehicles.get((trip["line"], str(trip["brigade"])))
            if row["vehicle_id"] is None:
                row["reason"] = "no_vehicle"
        out.append(row)
    return out
