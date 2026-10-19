"""RouteRequest.onboard: plan from the next two stops of the vehicle's trip (scheduled times, no live delay)."""
import pytest

import bus_detect
import street_router
from app.models import Place
from app.routing import geometry, onboard, real_engine as engine

from test_plan_engine import option, ride, walk
from test_station_routes import A, B, C, D, END, START, client, request, router  # noqa: F401  (router = fixture)

TRIP = "ztm:T9"
# the vehicle's trip: A 07:58:20, B 08:03:20, C 08:08:20, D 08:13:20 (seconds after the service day's midnight)
CALLS = [{"stop_id": s, "name": s, "lat": 52.25, "lon": 21.04, "arr": t, "dep": t, "shape_dist": i * 100}
         for i, (s, t) in enumerate(((A, 28700), (B, 29000), (C, 29300), (D, 29600)))]
HERE = (52.255, 21.045)


def live(next_stop=B, scheduled="08:03:20", delay=300, trip=TRIP):
    return {"vehicleId": "tram-1", "line": "9", "mode": "tram", "tripId": trip, "delaySec": delay,
            "nextStop": {"id": next_stop, "scheduled": scheduled, "expected": "08:08:20"} if next_stop else None}


@pytest.fixture
def vehicle(router, monkeypatch):
    sent = []
    answers = {
        B: [option([walk(B, None, 1500.0)], 29000),
            option([ride(B, D, TRIP, "9", 29000, 29600, "tram", wait=0.0), walk(D, None)], 29000)],
        C: [option([walk(C, None, 1500.0)], 29300),
            option([walk(C, A, 30.0, 40.0), ride(A, D, "ztm:T5", "175", 29400, 29500), walk(D, None)], 29300)],
    }

    def fake_plan(a, b, mode="walk", when=None, **options):
        sent.append({"from": a, "to": b, **options})
        return answers[a]

    state = {"live": live()}
    monkeypatch.setattr(bus_detect, "_need_data", lambda: None)
    monkeypatch.setattr(bus_detect, "_delay_for", lambda vehicle_id: state["live"] if vehicle_id == "tram-1" else None)
    monkeypatch.setitem(bus_detect._history, "tram-1", [{"lat": HERE[0], "lon": HERE[1], "t": 0}])
    monkeypatch.setattr(onboard, "_scheduled_calls", lambda trip_id: CALLS if trip_id == TRIP else [])
    monkeypatch.setattr(engine, "_plan_ready", lambda mode: True)
    monkeypatch.setattr(street_router, "plan", fake_plan)
    monkeypatch.setattr(geometry.mkuran, "trip_onward", lambda *args: [])
    return sent, state


def post(monkeypatch, **extra):
    body = request(onboard={"vehicleId": "tram-1"}, **extra).model_dump(by_alias=True, mode="json")
    return client(monkeypatch).post("/api/routes", json=body)


def test_plans_from_the_next_two_stops_at_their_scheduled_times(vehicle, monkeypatch):
    sent, _ = vehicle
    response = post(monkeypatch, excludeModes=["metro"])
    assert response.status_code == 200
    assert [(s["from"], s["time"]) for s in sent[::2]] == [(B, 29000), (C, 29300)]  # the delay (300 s) is ignored
    assert all(s["exclude_modes"] == ["metro"] for s in sent)


def test_prepended_ride_leg_and_titles(vehicle, monkeypatch):
    options = {o["id"]: o for o in post(monkeypatch).json()}
    bus = options["pt-ztm:T9-ztm:T5"]
    first = bus["legs"][0]
    assert (first["mode"], first["line"], first["tripId"], first["fromId"], first["toId"], first["waitS"]) == \
        ("tram", "9", TRIP, None, C, 0.0)
    assert first["from"] == "Obecna pozycja" and first["start"] == [HERE[1], HERE[0]]
    assert first["durationMin"] == 8  # now 08:00 -> scheduled arrival at C 08:08:20
    assert [leg["mode"] for leg in bus["legs"]] == ["tram", "walk", "bus", "walk"]
    assert bus["title"] == "9 + 175" and bus["transfers"] == 1 and bus["departure"] == "08:00"


def test_staying_on_the_same_trip_merges_into_one_ride(vehicle, monkeypatch):
    stay = {o["id"]: o for o in post(monkeypatch).json()}["pt-ztm:T9"]
    ride_leg = stay["legs"][0]
    assert [leg["mode"] for leg in stay["legs"]] == ["tram", "walk"]
    assert (ride_leg["fromId"], ride_leg["toId"], ride_leg["tripId"]) == (None, D, TRIP)
    assert stay["title"] == "9" and stay["transfers"] == 0
    assert ride_leg["durationMin"] == 3 + 10  # to B, then on to D


def test_options_are_sorted_by_arrival_deduped_and_tagged(vehicle, monkeypatch):
    options = post(monkeypatch).json()
    ids = [o["id"] for o in options]
    assert len(ids) == len(set(ids)) and len(options) <= 6
    assert ids[0] == "pt-ztm:T9-ztm:T5" and options[0]["tags"] == ["Najszybsza"]
    assert [o["arrival"] for o in options] == sorted(o["arrival"] for o in options)
    assert all(o["departure"] == "08:00" for o in options)


def test_without_a_known_next_stop_the_first_calls_after_now_are_used(vehicle, monkeypatch):
    sent, state = vehicle
    state["live"] = live(next_stop=None)
    assert post(monkeypatch).status_code == 200
    assert [s["from"] for s in sent[::2]] == [B, C]
    assert onboard.next_index(CALLS, None, None, 29100) == 2


@pytest.mark.parametrize("change", [
    {"vehicle": "tram-404"},
    {"live": live(trip=None)},
    {"live": live(next_stop=None), "late": True},
])
def test_unknown_vehicle_trip_or_stop_is_404(vehicle, monkeypatch, change):
    _, state = vehicle
    if "live" in change:
        state["live"] = change["live"]
    body = request(onboard={"vehicleId": change.get("vehicle", "tram-1")})
    if change.get("late"):
        body.when = "2026-10-18T09:00"
    response = client(monkeypatch).post("/api/routes", json=body.model_dump(by_alias=True, mode="json"))
    assert response.status_code == 404 and response.json() == {"detail": "vehicle not found"}


def test_onboard_with_via_is_422(vehicle, monkeypatch):
    response = post(monkeypatch, via=[Place(id="v", label="V", position=(52.231, 21.011))])
    assert response.status_code == 422


def test_no_live_data_is_503(router, monkeypatch):
    def missing():
        raise bus_detect.HTTPException(503, "no live vehicle data yet, try again in a few seconds")

    monkeypatch.setattr(bus_detect, "_need_data", missing)
    assert post(monkeypatch).status_code == 503
