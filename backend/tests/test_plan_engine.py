"""real_engine on the router's POST /plan: fake plan() answers -> RouteOptions; 503 when it is not ready."""
import pytest

import street_router
from app.routing import geometry, real_engine as engine

from test_station_routes import (  # noqa: F401  (router = the shared fixture)
    A, B, C, END, P, Q, START, client, request, router,
)


def walk(a, b, seconds=120.0, meters=150.0):
    return {"mode": "walk", "from": a, "to": b, "seconds": seconds, "walk_m": meters, "bike_m": 0.0, "wait_s": 0.0,
            "path": [[21.0100, 52.2300], [21.0105, 52.2305]], "segments": [], "elevators": [], "steps": []}


def ride(a, b, trip, line, dep, arr, mode="bus", wait=30.0):
    return {"mode": mode, "line": line, "route_id": line, "trip_id": trip, "headsign": "X", "from": a, "to": b,
            "dep_s": dep, "arr_s": arr, "seconds": wait + arr - dep, "wait_s": wait,
            "stops": [{"id": a, "arr_s": dep, "dep_s": dep}, {"id": b, "arr_s": arr, "dep_s": arr}]}


def bike(a, b):
    return {"mode": "veturilo", "from": a, "to": b, "seconds": 400.0, "walk_m": 0.0, "bike_m": 1500.0,
            "wait_s": 45.0, "pickup_s": 30.0, "return_s": 15.0, "path": [[21.0105, 52.2305], [21.0110, 52.2310]],
            "segments": [], "elevators": [], "steps": []}


def option(legs, dep, transfers=0):
    seconds = sum(leg["seconds"] for leg in legs)
    return {"seconds": seconds, "dep_s": dep, "arr_s": dep + seconds, "transfers": transfers,
            "walk_m": sum(leg.get("walk_m", 0) for leg in legs), "bike_m": sum(leg.get("bike_m", 0) for leg in legs),
            "wait_s": sum(leg["wait_s"] for leg in legs), "legs": legs}


WALK = option([walk(None, None, 1500.0, 1800.0)], 28800)
BUS = option([walk(None, A), ride(A, B, "ztm:T1", "175", 29000, 29600), walk(B, None)], 28880)
VETURILO = option([walk(None, P), bike(P, Q), walk(Q, None)], 28800)
TRANSFER = option([walk(None, A), ride(A, B, "ztm:T2", "18", 28950, 29200, "tram"), walk(B, C, 60.0, 80.0),
                   ride(C, B, "ztm:T3", "M1", 29300, 29400, "metro", 40.0), walk(B, None)], 28830, transfers=1)


@pytest.fixture
def plan(router, monkeypatch):
    sent = []
    answers = [[WALK, BUS, VETURILO, TRANSFER], []]

    def fake_plan(a, b, mode="walk", when=None, **options):
        sent.append({"from": a, "to": b, "mode": mode, **options})
        return answers[min(len(sent) - 1, len(answers) - 1)]

    monkeypatch.setattr(engine, "_plan_ready", lambda mode: True)
    monkeypatch.setattr(geometry.mkuran, "trip_onward", lambda *args: [])  # calls = the router's stops
    monkeypatch.setattr(street_router, "plan", fake_plan)
    return sent, answers


def test_plan_options_become_route_options(plan):
    sent, _ = plan
    options = engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00", search=request())
    by_id = {o.id: o for o in options}
    assert set(by_id) == {"walk", "pt-ztm:T1", "bike", "pt-ztm:T2-ztm:T3"}
    assert sent[0]["date"] == "20261018" and sent[0]["time"] == 28800 and sent[0]["max_legs"] == 3
    assert sent[0]["from"] == START.position and sent[0]["mode"] == "walk"
    assert sent[1]["time"] == 28800 + 60  # one later query from the earliest transit option's departure

    bus = by_id["pt-ztm:T1"]
    assert bus.title == "175" and bus.departure == "08:01" and bus.transfers == 0
    assert [leg.mode for leg in bus.legs] == ["walk", "bus", "walk"]
    ride_leg = bus.legs[1]
    assert (ride_leg.fromId, ride_leg.toId, ride_leg.tripId, ride_leg.waitS) == (A, B, "ztm:T1", 30.0)
    assert ride_leg.durationMin == 10 and len(ride_leg.path) >= 2
    assert bus.legs[0].fromId is None and bus.legs[0].from_ == "Start" and bus.legs[-1].to == "Cel"

    vet = by_id["bike"]
    assert vet.title == "Veturilo" and vet.legs[1].mode == "veturilo" and vet.bikeDistance == 1500.0
    assert vet.waitS == 45.0

    transfer = by_id["pt-ztm:T2-ztm:T3"]
    assert transfer.title == "18 + M1" and transfer.transfers == 1 and transfer.waitS == 70.0
    assert options[0].tags == ["Najszybsza"] and options == sorted(options, key=lambda o: o.durationMin)


def test_no_bike_speed_turns_veturilo_off_and_max_transfers_sets_the_legs(plan):
    sent, _ = plan
    engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                          search=request(bikeKmh=0, maxTransfers=0))
    assert sent[0]["veturilo_s"] == 0 and sent[0]["max_legs"] == 1


def test_step_free_plans_on_the_accessible_graph(plan):
    sent, _ = plan
    engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                          search=request(stepFree=True))
    assert sent[0]["mode"] == "accessible"


def test_long_street_only_trip_and_excluded_areas_are_dropped(plan):
    _, answers = plan
    answers[0] = [option([walk(None, None, 3600.0, 4000.0)], 28800), BUS]
    plain = engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00", search=request())
    assert [o.id for o in plain] == ["pt-ztm:T1"]
    answers[0] = [option([walk(None, A), ride(A, B, "ztm:T1", "175", 29000, 29600), walk(B, None)], 28880)]
    answers[0][0]["legs"][0]["path"] = [[21.0100, 52.2300], [21.0300, 52.2400], [21.0105, 52.2305]]
    middle = request(excludedPoints=[{"position": (52.2400, 21.0300), "radiusM": 50}])
    kept = engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00", search=middle)
    assert [o.id for o in kept] == ["walk"]  # the bus crosses the area; the walk (asked separately) does not


@pytest.mark.parametrize("failure, detail", [
    (NotImplementedError("x"), "transit timetable not ready: x"),
    (street_router.RouteError(503, "no timetable"), "no timetable"),
])
def test_plan_refusal_is_a_503_without_fallback(plan, monkeypatch, failure, detail):
    def refuse(*args, **kwargs):
        raise failure

    monkeypatch.setattr(street_router, "plan", refuse)
    response = client(monkeypatch).post("/api/routes", json=request().model_dump(by_alias=True, mode="json"))
    assert response.status_code == 503 and response.json() == {"detail": detail}


@pytest.mark.parametrize("health, ready", [
    ({"timetable": {"status": "ok"}, "plan": {"walk": "ok"}}, True),
    ({"timetable": {"status": "missing"}, "plan": {"walk": "no timetable"}}, False),
    ({"timetable": {"status": "ok"}, "plan": {"walk": "matrix stale"}}, False),
    ({"modes": {}}, False),  # an older router without /plan
])
def test_plan_ready_reads_health(monkeypatch, health, ready):
    monkeypatch.setattr(street_router, "health", lambda: health)
    assert engine._plan_ready("walk") is ready


def test_not_ready_router_answers_503(router, monkeypatch):
    monkeypatch.setattr(engine, "_plan_ready", lambda mode: False)
    monkeypatch.setattr(street_router, "plan", lambda *a, **k: pytest.fail("plan must not be called"))
    response = client(monkeypatch).post("/api/routes", json=request().model_dump(by_alias=True, mode="json"))
    assert response.status_code == 503 and response.json() == {"detail": "transit timetable not ready"}


def test_walk_is_added_when_plan_gives_no_street_only_trip(plan):
    _, answers = plan
    answers[0] = [BUS]
    ids = [o.id for o in engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                                                search=request())]
    assert sorted(ids) == ["pt-ztm:T1", "walk"]


def test_off_graph_point_gives_no_options_and_downtime_503(plan, monkeypatch):
    def off(*args, **kwargs):
        raise street_router.RouteError(422, "too far")

    monkeypatch.setattr(street_router, "plan", off)
    assert engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                                 search=request()) == []

    def down(mode):
        raise street_router.RouterUnavailable("down")

    monkeypatch.setattr(engine, "_plan_ready", down)
    response = client(monkeypatch).post("/api/routes", json=request().model_dump(by_alias=True, mode="json"))
    assert response.status_code == 503
