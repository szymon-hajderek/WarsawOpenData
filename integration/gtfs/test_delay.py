"""Scenario 3: the vehicle of the planned ride is 4 min late. The route must move by those 4 min and the
user, who leaves at the new time, must still catch it."""
import random

import pytest

import results
from journey import planned_epoch, replay_of, travel
from planning import plan, rides, surface_transit
from sim import api as sim_api
from sim import clock

pytestmark = pytest.mark.gtfs


def test_delay_moves_the_route(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("delay-zbawiciela-wilanowska")
    trip, delay = sc.spec["trip"], sc.spec["test"]["delay_s"]
    asked = clock.now()
    before = surface_transit(plan(client, trip))
    assert before, "no bus / tram option"
    ride = rides(before)[0]

    sc.set_delay(ride["line"], ride["brigade"], delay)
    after_all = plan(client, trip)
    after = next((o for o in after_all if o["id"] == before["id"]), None)
    assert after, f"the delayed option is gone: {[o['title'] for o in after_all]}"
    shift = planned_epoch(asked, after["arrival"]) - planned_epoch(asked, before["arrival"])

    sim_api.step(to=max(clock.now(), planned_epoch(asked, after["departure"])))
    run = travel(client, after, trip["profile"], random.Random(3))
    late_s = run["trip"].end - planned_epoch(asked, after["arrival"])
    # lateness.py measures the delay at the nearest stop, so it can be up to about a minute short
    tags = [t for t in after["tags"] if t.startswith("opóźnienie ")]
    tag_min = int(tags[0].split()[1]) if tags else None

    checks = [
        (f"arrival moves by the delay ({delay} s +- 90 s)", abs(shift - delay) <= 90),
        (f"the option has the tag 'opóźnienie N min' with N = {delay // 60} +- 1",
         tag_min is not None and abs(tag_min - delay / 60) <= 1),
        ("the option had no delay tag before", not any(t.startswith("opóźnienie") for t in before["tags"])),
        (f"travel finished ({run['trip'].reason or 'ok'})", run["trip"].ok),
        ("the user leaving at the new time arrives no later than the new plan + 3 min", late_s <= 180),
    ]
    results.record("delay-zbawiciela-wilanowska", sc.spec["title"], "gtfs", {
        "option": before["title"], "delayed vehicle": f"line {ride['line']}, brigade {ride['brigade']}",
        "set delay (s)": delay, "plan before": f"{before['departure']}-{before['arrival']}",
        "plan after": f"{after['departure']}-{after['arrival']}", "arrival shift (s)": shift,
        "arrival vs new plan (s, + = late)": late_s, "tags after": ", ".join(after["tags"]),
    }, checks, replay=replay_of(after, run))
    for name, ok in checks:
        assert ok, name
