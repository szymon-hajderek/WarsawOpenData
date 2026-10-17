"""Scenario 2: plan a trip with /api/routes, then travel it with synthetic vehicles from the timetable.

The user leaves at the planned time, walks to the stop, waits for a vehicle of the planned line, rides
it (bus detection must find it) and walks to the destination.
"""
import random

import pytest

import results
from config import haversine_m
from journey import planned_epoch, replay_of, travel
from planning import plan, surface_transit
from sim import api as sim_api
from sim import clock

pytestmark = pytest.mark.gtfs

ARRIVAL_SLACK_S = 3 * 60
END_RADIUS_M = 150


def test_travel_the_planned_trip(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("trip-gorczewska-daszynskiego")
    trip = sc.spec["trip"]
    options = plan(client, trip)
    option = surface_transit(options)
    assert option, f"no bus / tram option among {[o['title'] for o in options]}"

    asked = clock.now()
    sim_api.step(to=max(asked, planned_epoch(asked, option["departure"])))  # leave at the planned time
    run = travel(client, option, trip["profile"], random.Random(11), sigma_m=15)
    t = run["trip"]
    end = t.fixes[-1]
    to = trip["to"]["position"]
    planned = planned_epoch(run["start"], option["arrival"])
    late_s = t.end - planned
    gap_m = haversine_m(end.true_lat, end.true_lon, to[0], to[1])
    ranks = run["ranks"]
    top4 = sum(r is not None for r in ranks) / max(1, len(ranks))
    boards = [e for e in t.events if e["event"] == "board"]

    checks = [
        (f"travel finished ({t.reason or 'ok'})", t.ok),
        (f"the user ends within {END_RADIUS_M} m of the destination", gap_m <= END_RADIUS_M),
        ("the user arrives no later than the planned arrival + 3 min", late_s <= ARRIVAL_SLACK_S),
        ("a vehicle of every planned line was boarded",
         [b["line"] for b in boards] == [leg["line"] for leg in option["legs"] if leg["mode"] in ("bus", "tram")]),
        ("bus detection has the ridden vehicle in the top 4 for at least 90% of requests", top4 >= 0.9),
    ]
    results.record("trip-gorczewska-daszynskiego", sc.spec["title"], "gtfs", {
        "option": option["title"], "planned": f"{option['departure']}-{option['arrival']}",
        "leaves after the query (min)": (run["start"] - asked) / 60,
        "planned duration (min)": option["durationMin"], "travel time (min)": (t.end - run["start"]) / 60,
        "arrival vs plan (s, + = late)": late_s, "end to destination (m)": gap_m,
        "waited at the stop (s)": sum(b["waited_s"] for b in boards),
        "detection requests while riding": len(ranks), "ridden vehicle in top 4 (%)": 100 * top4,
        "ridden vehicle first (%)": 100 * sum(r == 1 for r in ranks) / max(1, len(ranks)),
    }, checks, replay=replay_of(option, run))
    for name, ok in checks:
        assert ok, name
