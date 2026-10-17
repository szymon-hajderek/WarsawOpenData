"""The demo API: list the scenarios, simulate a ride of a chosen option and return its timeline."""
import pytest

from planning import plan, surface_transit

pytestmark = pytest.mark.gtfs


def test_scenarios_are_listed(client):
    names = {s["name"] for s in client.get("/api/sim/scenarios").json()}
    assert {"trip-gorczewska-daszynskiego", "delay-wilenski-waszyngtona"} <= names


def test_ride_returns_a_timeline(client, gtfs_ready, osm_ready, scenario):
    sc = scenario("trip-gorczewska-daszynskiego")
    trip = sc.spec["trip"]
    option = surface_transit(plan(client, trip))
    assert option, "no bus / tram option"
    before = client.get("/api/sim/state").json()["t"]

    r = client.post("/api/sim/ride", json={"option": option, "profile": trip["profile"], "noiseM": 20, "seed": 3})
    assert r.status_code == 200, r.text
    ride = r.json()
    assert ride["ok"], ride["reason"]
    times = [f["t"] for f in ride["fixes"]]
    assert times == sorted(times) and len(times) > 20
    surface = [leg for leg in option["legs"] if leg["mode"] in ("bus", "tram")]
    assert [e["event"] for e in ride["events"]].count("board") == len(surface)
    assert ride["detections"], "no vehicle detection while riding"
    assert len(ride["plan"]) == len(option["legs"])
    # the clock is back at the scenario start, so a second ride starts from the same state
    assert client.get("/api/sim/state").json()["t"] == before


def test_ride_rejects_a_broken_option(client, scenario):
    scenario("trip-gorczewska-daszynskiego")
    r = client.post("/api/sim/ride", json={"option": {"legs": []}})
    assert r.status_code == 422
