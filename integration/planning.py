"""Asking the route API from tests, and reading the option it returns."""
from __future__ import annotations

import re

TRIP_ID = re.compile(r"(?:ztm|wkd|pkp):.+?(?=-(?:ztm|wkd|pkp):|$)")


def plan(client, trip: dict, when: str | None = None) -> list[dict]:
    """POST /api/routes. The route engine reads the real clock, so the simulated time goes in `when`."""
    from sim import clock

    body = {"from": trip["from"], "to": trip["to"], "profile": trip.get("profile", "standard"),
            "when": when or clock.warsaw_now().isoformat(timespec="seconds")}
    r = client.post("/api/routes", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def surface_transit(options: list[dict]) -> dict | None:
    """The fastest option with a bus or tram and no metro / rail (those have no live feed)."""
    for o in options:
        modes = {leg["mode"] for leg in o["legs"]}
        if modes & {"bus", "tram"} and not modes & {"metro", "rail"}:
            return o
    return None


def bike_option(options: list[dict]) -> dict | None:
    return next((o for o in options if [leg["mode"] for leg in o["legs"]] == ["walk", "bike", "walk"]), None)


def rides(option: dict) -> list[dict]:
    """The GTFS trips of a transit option ("pt-<trip id>-<trip id>"), with line and brigade."""
    from sources import mkuran

    if not option["id"].startswith("pt-"):
        return []
    ids = TRIP_ID.findall(option["id"][3:])
    by_id = {t[0]: t for t in mkuran.trips() if t[0] in ids}
    routes = mkuran.routes()
    return [{"trip_id": i, "line": routes[by_id[i][1]]["short_name"], "brigade": by_id[i][3]}
            for i in ids if i in by_id]


def lines(option: dict) -> set[str]:
    return {leg["line"] for leg in option["legs"] if leg.get("line")}
