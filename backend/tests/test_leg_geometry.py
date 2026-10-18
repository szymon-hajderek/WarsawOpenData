"""Router answer formats (old and agreed new) and leg geometry, without data files."""
import pytest

import street_router
from app.routing import geometry, real_engine as engine
from test_station_routes import (  # noqa: F401  (router = the shared fixture)
    _RIDE_PATH, A, B, C, D, END, NOW, P, Q, START, client, request, ride, router,
)


def _new_format(old):
    """The agreed router format of an old /route answer: legs only, ends as id / null, elevators per leg."""
    legs = []
    for leg in old["legs"]:
        leg = {**leg, "from": leg["from"]["id"], "to": leg["to"]["id"]}
        leg.update(elevators=old.get("elevators", []), steps=old.get("steps", []))
        legs.append(leg)
    return {"legs": legs}


@pytest.mark.parametrize("a,b,mode", [(START.position, A, "walk"), (A, END.position, "accessible"),
                                      (START.position, END.position, "bike"), (A, B, "walk")])
def test_adapter_gives_the_same_legs_for_the_old_and_the_new_format(router, a, b, mode):
    _, _, answer = router
    old = answer(a, b, mode)
    old["steps"] = [old["path"][0]]
    new = _new_format(old)
    assert "seconds" not in new and all(not isinstance(leg["from"], dict) for leg in new["legs"])
    got_old = engine.legs_from_router(old, from_name="S", to_name="E", points=(a, b))
    got_new = engine.legs_from_router(new, from_name="S", to_name="E", points=(a, b))
    assert [leg.model_dump(by_alias=True) for leg in got_old] == [leg.model_dump(by_alias=True) for leg in got_new]
    leg, = got_new
    assert leg.steps == [tuple(leg.path[0])]
    assert leg.elevators == ([tuple(leg.path[0])] if mode == "accessible" else [])
    assert leg.waitS is None and leg.tripId is None and leg.approximatePath is False
    assert engine._seconds(new) == engine._seconds(old)


def _future_trip(locations):
    """A /plan-style answer: walk -> Veturilo -> walk -> bus (no shape) -> walk, ends as ids / null."""
    def pos(station_id):
        p = locations[station_id]["position"]
        return [p["lon"], p["lat"]]

    def street(mode, a, b, start, end, wait_s=0.0):
        return {"mode": mode, "from": a, "to": b, "seconds": 100.0, "walk_m": 50.0,
                "bike_m": 400.0 if mode == "veturilo" else 0.0, "wait_s": wait_s, "path": [start, end],
                "segments": [{"kind": "walk", "path": [start, end], "length_m": 50.0}],
                "elevators": [], "steps": []}

    start, end = list(START.position[::-1]), list(END.position[::-1])
    veturilo = street("veturilo", P, Q, pos(P), pos(Q), wait_s=12.0)
    veturilo.update(pickup_s=30, return_s=20)
    bus = {"mode": "bus", "line": "175", "route_id": "ztm:175", "trip_id": "ztm:175:1", "headsign": "Dworzec",
           "from": A, "to": C, "dep_s": 29400, "arr_s": 30000, "seconds": 720, "wait_s": 120,
           "stops": [{"id": A, "arr_s": 29400, "dep_s": 29400}, {"id": B, "arr_s": 29700, "dep_s": 29700},
                     {"id": C, "arr_s": 30000, "dep_s": 30000}]}
    return {"legs": [street("walk", None, P, start, pos(P), wait_s=5.0), veturilo,
                     street("walk", Q, A, pos(Q), pos(A)), bus, street("walk", C, None, pos(C), end)]}


def _no_shapes(monkeypatch):
    monkeypatch.setattr(geometry, "_ride_path", _RIDE_PATH)
    monkeypatch.setattr(geometry.mkuran, "trip_onward", lambda *args: [])
    monkeypatch.setattr(geometry.mkuran, "trip_shape_id", lambda trip_id: "")
    monkeypatch.setattr(geometry.mkuran, "shape_slice", lambda *args: [])
    monkeypatch.setattr(geometry.mkuran, "shape_by_stops", lambda *args: [])


def test_future_transit_and_veturilo_legs_convert(router, monkeypatch):
    _, locations, _ = router
    _no_shapes(monkeypatch)

    def lonlat(station_id):
        p = locations[station_id]["position"]
        return (p["lon"], p["lat"])

    legs = engine.legs_from_router(_future_trip(locations), from_name="Start", to_name="Cel",
                                   points=(START.position, END.position))
    walk_in, bike, walk, bus, walk_out = legs
    assert [leg.mode for leg in legs] == ["walk", "veturilo", "walk", "bus", "walk"]
    assert [(leg.fromId, leg.toId) for leg in legs] == [(None, P), (P, Q), (Q, A), (A, C), (C, None)]
    assert walk_in.start == START.position[::-1] and walk_out.end == END.position[::-1]
    assert (bike.start, bike.end, bus.start, bus.end) == (lonlat(P), lonlat(Q), lonlat(A), lonlat(C))
    for previous, following in zip(legs, legs[1:]):
        assert previous.end == following.start
    assert (bus.line, bus.tripId, bus.waitS, bus.durationMin) == ("175", "ztm:175:1", 120, 10)
    assert bus.approximatePath is True
    assert bus.path == [lonlat(s)[::-1] for s in (A, B, C)]
    assert bus.from_ == A and bus.to == C  # overlay names
    assert bike.approximatePath is False and bike.waitS is None and bike.distanceM == 450
    option = engine._option("plan", "Plan", legs, NOW)
    assert option.waitS == 120 + 5 + 12  # transit wait + street waits
    assert option.bikeDistance == 400 and option.transfers == 0


def test_leg_path_per_leg_type_and_fallback(router, monkeypatch):
    _, locations, _ = router
    _no_shapes(monkeypatch)
    trip = _future_trip(locations)
    walk = trip["legs"][0]
    assert geometry.leg_path(walk, START.position, None) == ([p[::-1] for p in walk["path"]], False)
    bus = trip["legs"][3]
    a, b, c = (locations[s]["position"] for s in (A, B, C))
    assert geometry.leg_path(bus) == ([[p["lat"], p["lon"]] for p in (a, b, c)], True)
    # A street leg without a path: a straight line between its ends (null = the query point).
    assert geometry.leg_path({**walk, "path": []}, START.position, None) == (
        [list(START.position), [locations[P]["position"]["lat"], locations[P]["position"]["lon"]]], True)
    # Router transit leg: the mkuran calls of the trip, cut at `to`, give the GTFS shape.
    shape = [[52.25, 21.04], [52.255, 21.045], [52.26, 21.05]]
    calls = [{"stop_id": s, "lat": 52.25, "lon": 21.04, "shape_dist": i * 100} for i, s in enumerate((A, B, C, D))]
    seen = []
    monkeypatch.setattr(geometry.mkuran, "trip_onward", lambda trip_id, stop_id, sec: calls)
    monkeypatch.setattr(geometry.mkuran, "trip_shape_id", lambda trip_id: "shape")
    monkeypatch.setattr(geometry.mkuran, "shape_slice", lambda shape_id, d0, d1: seen.append((d0, d1)) or shape)
    assert geometry.leg_path(bus) == (shape, False)
    assert seen == [(0, 200)]  # cut at C, not D
    # mkuran calls given directly (today's planner).
    assert geometry.leg_path({"mode": "tram", "trip_id": "t", "from": A, "to": B}, calls=calls[:2]) == (shape, False)


def test_position_resolves_ids_and_query_points(router):
    _, locations, _ = router
    a = (locations[A]["position"]["lat"], locations[A]["position"]["lon"])
    assert geometry.position(A, None) == a
    assert geometry.position(None, START.position) == START.position
    assert geometry.position(None, A) == a  # the query point may itself be an id
    assert geometry.position("ztm:unknown", START.position) == START.position


def test_new_format_bike_trip_keeps_segments_and_wait(router, monkeypatch):
    _, _, answer = router
    monkeypatch.setattr(street_router, "route", lambda a, b, mode="walk", **kw: _new_format(answer(a, b, mode, **kw)))
    response = client(monkeypatch).post("/api/routes", json=request(travel="bike").model_dump(by_alias=True))
    assert response.status_code == 200
    option, = response.json()
    leg, = option["legs"]
    assert [s["kind"] for s in leg["segments"]] == ["push", "ride"]
    assert leg["start"] == list(START.position[::-1]) and leg["end"] == list(END.position[::-1])
    assert leg["elevators"] == [] and leg["steps"] == [] and leg["waitS"] is None
    assert option["bikeDistance"] == 500 and option["waitS"] == 0
