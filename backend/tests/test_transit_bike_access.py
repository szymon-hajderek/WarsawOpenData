"""Transit with the own bike (`access: "bike"`): /plan in mode bike -> bike + transit options; 422 with a wheelchair."""
import pytest

from app.routing import real_engine as engine

from test_plan_engine import option, plan, ride  # noqa: F401  (plan = the fake /plan fixture)
from test_station_routes import A, B, C, END, START, client, request, router  # noqa: F401


def own_bike(a, b, ridden=2000.0, pushed=50.0, wait=20.0):
    """An own-bike street leg in /plan mode bike: ridden and pushed metres, with segments."""
    seconds = ridden / 4.2 + pushed / 1.3 + wait
    return {"mode": "bike", "from": a, "to": b, "seconds": seconds, "walk_m": pushed, "bike_m": ridden,
            "wait_s": wait, "path": [[21.0100, 52.2300], [21.0105, 52.2305]],
            "segments": [{"kind": "push", "path": [[21.0100, 52.2300], [21.0101, 52.2301]], "length_m": pushed},
                         {"kind": "ride", "path": [[21.0101, 52.2301], [21.0105, 52.2305]], "length_m": ridden}],
            "elevators": [], "steps": []}


BIKE_ONLY = option([own_bike(None, None, 9000.0, 30.0)], 28800)
BIKE_BUS = option([own_bike(None, A), ride(A, B, "ztm:T1", "502", 29300, 29900), own_bike(B, None, 1500.0, 0.0)],
                  28800)
# a metro transfer walked with the bike (bike_m 0) does not show as "Rower" in the title; two ridden legs in a row
# (to another stop, then to the destination) show once
BIKE_TRANSFER = option([own_bike(None, A), ride(A, B, "ztm:T2", "18", 29000, 29200, "tram"),
                        own_bike(B, C, 0.0, 200.0, 60.0), ride(C, B, "ztm:T3", "M1", 29500, 29600, "metro"),
                        own_bike(B, C, 300.0, 0.0), own_bike(C, None, 800.0, 0.0)], 28700, transfers=1)


def test_bike_access_plans_in_bike_mode_with_own_bike_legs(plan):
    sent, answers = plan
    answers[0] = [BIKE_ONLY, BIKE_BUS, BIKE_TRANSFER]
    options = engine.RealRouteEngine().query_routes(
        START, END, "standard", when="2026-10-18T08:00", search=request(access="bike", bikeKmh=18, walkKmh=4.5))
    assert sent[0]["mode"] == "bike" and "veturilo_s" not in sent[0]
    assert sent[0]["speeds"] == {"walk": 4.5 / 3.6, "bike": 18 / 3.6}
    by_id = {o.id: o for o in options}
    assert set(by_id) == {"bike", "pt-ztm:T1", "pt-ztm:T2-ztm:T3"}

    alone = by_id["bike"]
    assert alone.title == "Własny rower" and [leg.mode for leg in alone.legs] == ["bike"]

    bus = by_id["pt-ztm:T1"]
    assert bus.title == "Rower + 502 + Rower" and bus.transfers == 0
    assert [leg.mode for leg in bus.legs] == ["bike", "bus", "bike"]
    assert bus.bikeDistance == 3500.0 and bus.walkDistance == 50.0
    assert bus.waitS == 20.0 + 30.0 + 20.0  # street waits + the wait at the boarding stop
    assert [s.kind for s in bus.legs[0].segments] == ["push", "ride"]
    assert not any(leg.mode == "veturilo" for o in options for leg in o.legs)

    transfer = by_id["pt-ztm:T2-ztm:T3"]
    assert transfer.title == "Rower + 18 + M1 + Rower" and transfer.transfers == 1


def test_bike_access_ignores_zero_bike_speed_and_keeps_excluded_modes(plan):
    sent, answers = plan
    answers[0] = [BIKE_BUS]
    options = engine.RealRouteEngine().query_routes(
        START, END, "standard", when="2026-10-18T08:00",
        search=request(access="bike", bikeKmh=0, excludeModes=["tram", "veturilo"]))
    assert sent[0]["mode"] == "bike" and "veturilo_s" not in sent[0]
    assert sent[0]["speeds"]["bike"] == engine.OSM_SPEED["bike"]  # bikeKmh 0 only means "no Veturilo"
    assert sent[0]["exclude_modes"] == ["tram", "veturilo"]
    by_id = {o.id: o for o in options}
    assert set(by_id) == {"pt-ztm:T1", "bike"}
    # /plan gave no street-only trip: it is asked from /route, ridden (not walked)
    assert by_id["bike"].title == "Własny rower" and [leg.mode for leg in by_id["bike"].legs] == ["bike"]


def test_walk_access_is_unchanged(plan):
    sent, _ = plan
    engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00", search=request(access="walk"))
    assert sent[0]["mode"] == "walk"


@pytest.mark.parametrize("extras", [
    {"profile": "accessible"}, {"profile": "stroller"}, {"travel": "accessible"}, {"travel": "stroller"},
    {"stepFree": True}, {"body": {"wheelchair": "manual"}},
])
def test_bike_access_with_a_wheelchair_or_stroller_is_422(plan, monkeypatch, extras):
    body = {"from": START.model_dump(), "to": END.model_dump(), "access": "bike", **extras}
    response = client(monkeypatch).post("/api/routes", json=body)
    assert response.status_code == 422 and "access 'bike'" in response.text
    assert plan[0] == []  # /plan was not asked
