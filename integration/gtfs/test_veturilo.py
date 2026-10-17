"""Scenario 4: a Veturilo trip. The pickup station runs out of bikes 5 min later; from then on the
route must not send the user there."""
import pytest

import results
from config import haversine_m
from planning import bike_option, plan
from sim import api as sim_api

pytestmark = pytest.mark.gtfs


def _station_id(name: str, near) -> str:
    from sources import nextbike

    same = [s for s in nextbike.stations() if s["name"] == name]
    assert same, f"no Veturilo station named {name}"
    return min(same, key=lambda s: haversine_m(s["lat"], s["lon"], near[0], near[1]))["station_id"]


def _bikes(station_id: str) -> int:
    from sources import nextbike

    return next(s["bikes"] for s in nextbike.status() if s["station_id"] == station_id)


def test_empty_station_is_avoided(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("veturilo-kabaty-ursynow")
    trip, after_s = sc.spec["trip"], sc.spec["test"]["empty_after_s"]
    first = bike_option(plan(client, trip))
    assert first, "no Veturilo option"
    pickup = first["legs"][1]["from"]
    station = _station_id(pickup, first["legs"][1]["path"][0])
    bikes_before = _bikes(station)
    sc.set_station(station, 0, at=sc.start + after_s)

    still = bike_option(plan(client, trip))
    sim_api.step(after_s)
    bikes_after = _bikes(station)
    later_all = plan(client, trip)
    later = bike_option(later_all)
    later_pickup = later["legs"][1]["from"] if later else None
    used = [o["title"] for o in later_all if any(leg["mode"] == "bike" and leg["from"] == pickup for leg in o["legs"])]

    checks = [
        ("the pickup station has bikes at the start", bikes_before > 0),
        ("before the change the route still starts there", still is not None and still["legs"][1]["from"] == pickup),
        ("the change shows in /api/veturilo status after 5 min", bikes_after == 0),
        ("after the change no option picks up a bike there", not used),
    ]
    results.record("veturilo-kabaty-ursynow", sc.spec["title"], "gtfs", {
        "pickup": pickup, "bikes before": bikes_before, "bikes after": bikes_after,
        "pickup after the change": later_pickup or "(no Veturilo option)",
        "plan before": f"{first['departure']}-{first['arrival']} ({first['durationMin']} min)",
        "plan after": f"{later['departure']}-{later['arrival']} ({later['durationMin']} min)" if later else "-",
    }, checks, replay={"plan": [{"mode": leg["mode"], "line": None, "path": leg["path"]} for leg in first["legs"]],
                       "after": [{"mode": leg["mode"], "line": None, "path": leg["path"]}
                                 for leg in (later["legs"] if later else [])]})
    for name, ok in checks:
        assert ok, name
