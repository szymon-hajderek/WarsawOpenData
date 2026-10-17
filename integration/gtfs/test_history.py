"""Scenario 6: a walk + Veturilo ride recorded as on the phone (a fix every 4 s), sent to the speed
history API. The averages must match the speeds the synthetic user moved at."""
import random

import pytest

import results
from app.routing.real_engine import PROFILE_SPEED
from sim.journey import planned_epoch, replay_of, travel
from planning import bike_option, plan
from sim import api as sim_api
from sim import clock

pytestmark = pytest.mark.gtfs


def test_speed_history_matches_the_ride(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("history-veturilo-ride")
    trip, spec = sc.spec["trip"], sc.spec["test"]
    option = bike_option(plan(client, trip))
    assert option, "no Veturilo option"
    sim_api.step(to=max(clock.now(), planned_epoch(clock.now(), option["departure"])))
    run = travel(client, option, trip["profile"], random.Random(5), sigma_m=spec["noise_m"],
                 step_s=spec["record_every_s"])
    track = [{"lat": f.lat, "lon": f.lon, "t": f.t} for f in run["trip"].fixes]
    legs = [{"mode": leg["mode"], "distanceM": leg["distanceM"]} for leg in option["legs"]]

    r = client.post("/api/history/records", json={"track": track, "legs": legs, "walkAs": "walking"})
    assert r.status_code == 200, r.text
    records = r.json()["records"]
    s = client.post("/api/history/summary", json={"records": records, "minTrips": 1})
    assert s.status_code == 200, s.text
    summary = s.json()

    speed = PROFILE_SPEED[trip["profile"]]
    want = {"walking": speed["walk"] * 3.6, "cycling": speed["bike"] * 3.6}
    got = {mode: summary[mode]["avgKmh"] for mode in want}
    tol = spec["tolerance"]
    checks = [(f"{mode}: average {got[mode]} km/h within {int(tol * 100)}% of {want[mode]:.1f} km/h",
               got[mode] is not None and abs(got[mode] - want[mode]) <= tol * want[mode]) for mode in want]
    checks.append(("the records carry no coordinates", all(set(rec) == {"mode", "distanceM", "durationS", "kmh", "at"}
                                                         for rec in records)))
    results.record("history-veturilo-ride", sc.spec["title"], "gtfs", {
        "fixes sent": len(track), "records": len(records),
        **{f"{mode} simulated (km/h)": want[mode] for mode in want},
        **{f"{mode} from history (km/h)": got[mode] for mode in want},
    }, checks, replay=replay_of(option, run))
    for name, ok in checks:
        assert ok, name
