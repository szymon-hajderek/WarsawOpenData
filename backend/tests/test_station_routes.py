"""Route engine with the station overlay and the router (street trips, the adapter), without data files."""
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import street_router
from app.api import routes
from app.models import Place, RouteRequest
from app.routing import geometry, real_engine as engine

_RIDE_PATH = geometry._ride_path  # the real one; the fixture stubs it

A, B, C, D = "ztm:A", "ztm:B", "ztm:C", "ztm:D"
P, Q = "vet:P", "vet:Q"
START = Place(id="start", label="Start", position=(52.2300, 21.0100))
END = Place(id="end", label="Cel", position=(52.2330, 21.0130))
NOW = datetime(2026, 10, 18, 8)


@pytest.fixture
def router(monkeypatch):
    locations = [{
        "id": station_id, "name": station_id, "kind": "bus_post",
        "position": {"lat": 52.2305 + i * 0.0002, "lon": 21.0105 + i * 0.0002},
        "gtfs": {"lat": 52.25 + i * 0.001, "lon": 21.04 + i * 0.001},
    } for i, station_id in enumerate((A, B, C, D, P, Q))]
    by_id = {loc["id"]: loc for loc in locations}
    monkeypatch.setattr(geometry.stations, "locations", lambda: locations)
    engine._overlay.cache_clear()
    calls = []

    def point(value):
        if isinstance(value, str):
            pos = by_id[value]["position"]
            return (pos["lat"], pos["lon"])
        return tuple(value)

    def answer(a, b, mode="walk", **options):
        calls.append((a, b, mode, options))
        start, end = point(a)[::-1], point(b)[::-1]
        path = [start, end]
        bike = mode == "bike"
        parts = [{"kind": "walk", "path": path, "length_m": 100}]
        if bike:
            middle = tuple((x + y) / 2 for x, y in zip(start, end))
            path = [start, middle, end]
            parts = [{"kind": "push", "path": [start, middle], "length_m": 10},
                     {"kind": "ride", "path": [middle, end], "length_m": 500}]
        leg = {"mode": "bike" if bike else "walk", "seconds": 180 if bike else 60,
               "from": {"id": a if isinstance(a, str) else None, "lonlat": start},
               "to": {"id": b if isinstance(b, str) else None, "lonlat": end},
               "walk_m": 10 if bike else 100, "bike_m": 500 if bike else 0,
               "wait_s": 0, "path": path, "segments": parts}
        return {**{key: leg[key] for key in ("seconds", "walk_m", "bike_m", "wait_s", "path")},
                "length_m": 510 if bike else 100, "geometry": [p[::-1] for p in path],
                "elevators": [start] if mode in ("accessible", "stroller") else [], "legs": [leg]}

    def access(point, mode="walk", direction="from", limit_s=900, **options):
        calls.append(("access", point, mode, direction, options))
        return [{"id": station_id, "seconds": 20 + i, "walk_m": 50, "bike_m": 0, "wait_s": 0}
                for i, station_id in enumerate((A, B, C, D))]

    monkeypatch.setattr(street_router, "route", answer)
    monkeypatch.setattr(street_router, "access", access)
    monkeypatch.setattr(engine.alerts, "alerted_lines", lambda: set())
    monkeypatch.setattr(geometry, "_ride_path", lambda *args: [[52.25, 21.04], [52.26, 21.05]])
    yield calls, by_id, answer
    engine._overlay.cache_clear()


def ride(a=A, b=B, departure=29400, arrival=30000, line="175"):
    calls = [{"stop_id": station_id, "name": station_id, "lat": 52.25, "lon": 21.04,
              "dep": seconds, "arr": seconds, "shape_dist": i * 100}
             for i, (station_id, seconds) in enumerate(((a, departure), (b, arrival)))]
    return {"dep": {"sec": departure, "trip_id": line, "mode": "bus", "line": line}, "calls": calls}


def request(**options):
    return RouteRequest(from_=START, to=END, when="2026-10-18T08:00", **options)


def client(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, "engine", engine.RealRouteEngine())
    return TestClient(app)


@pytest.mark.parametrize("travel,profile,extras,graph", [
    ("walk", "standard", {}, "walk"),
    ("walk", "accessible", {}, "accessible"),
    ("walk", "standard", {"stepFree": True}, "accessible"),
    ("walk", "standard", {"body": {"wheelchair": "manual"}}, "accessible"),
    ("walk", "stroller", {}, "stroller"),
    ("accessible", "standard", {}, "accessible"),
    ("stroller", "standard", {}, "stroller"),
    ("bike", "standard", {}, "bike"),
])
def test_street_only_modes_use_effective_speeds_without_timetable_or_live_data(router, monkeypatch, travel, profile, extras, graph):
    calls, _, _ = router

    def forbidden(*args):
        pytest.fail("Street-only requests must not load the timetable or live feeds")

    monkeypatch.setattr(geometry.stations, "locations", forbidden)
    monkeypatch.setattr(street_router, "plan", forbidden)
    req = request(travel=travel, profile=profile, walkKmh=3.6, bikeKmh=18, **extras)
    option, = engine.RealRouteEngine().query_routes(START, END, profile, req.when, req)
    cycling_disabled = profile in ("accessible", "stroller") or travel in ("accessible", "stroller") or "body" in extras
    speeds = {"walk": 1, "bike": 4.2 if cycling_disabled else 5}
    assert calls == [(START.position, END.position, graph, {"speeds": speeds})]
    assert option.legs[0].from_ == "Start" and option.legs[0].to == "Cel"
    assert option.legs[0].fromId is None and option.legs[0].toId is None
    assert ("bez schodów" in option.tags) == (graph in ("accessible", "stroller"))
    assert ("windy: 1" in option.tags) == (graph in ("accessible", "stroller"))
    assert option.bikeDistance == (500 if graph == "bike" else 0)
    assert option.walkDistance == (10 if graph == "bike" else 100)


def test_adapter_multi_leg_names_coordinate_conversion_and_optional_segments(router):
    _, _, answer = router
    first, second = answer(START.position, A), answer(A, END.position)
    raw = {"legs": [first["legs"][0], second["legs"][0]]}
    raw["legs"][1].pop("segments")
    legs = engine.legs_from_router(raw, {A: "Stop"}, from_name="Start", to_name="Cel")
    assert [(leg.from_, leg.to) for leg in legs] == [("Start", "Stop"), ("Stop", "Cel")]
    assert legs[0].path[-1] == legs[0].end[::-1]
    assert legs[0].segments[0].path == legs[0].path and legs[0].segments[0].lengthM == 100
    assert legs[1].segments == []
    assert raw["legs"][0]["path"][0] == START.position[::-1]  # adapter does not mutate the answer.


@pytest.mark.parametrize("status", [404, 422])
def test_mixed_street_errors_drop_candidates_but_explicit_requests_keep_status(router, monkeypatch, status):
    def failure(*args, **kwargs):
        raise street_router.RouteError(status, "no street path")

    monkeypatch.setattr(street_router, "route", failure)
    monkeypatch.setattr(street_router, "access", failure)
    assert engine._street(START.position, A, "walk", "accessible") is None
    req = request(travel="accessible")
    response = client(monkeypatch).post("/api/routes", json=req.model_dump(by_alias=True))
    assert response.status_code == status


@pytest.mark.parametrize("travel", ["walk", "accessible", "stroller", "bike", "transit"])
def test_router_downtime_returns_503(router, monkeypatch, travel):
    def unavailable(*args, **kwargs):
        raise street_router.RouterUnavailable("router stopped")

    monkeypatch.setattr(street_router, "route", unavailable)
    monkeypatch.setattr(street_router, "access", unavailable)
    monkeypatch.setattr(street_router, "health", unavailable)
    response = client(monkeypatch).post("/api/routes", json=request(travel=travel).model_dump(by_alias=True))
    assert response.status_code == 503 and response.json()["detail"] == "router stopped"


def test_street_only_via_keeps_segments_and_totals(router, monkeypatch):
    req = request(travel="bike", via=[Place(id="via", label="Via", position=(52.231, 21.011))])
    response = client(monkeypatch).post("/api/routes", json=req.model_dump(by_alias=True))
    assert response.status_code == 200
    option, = response.json()
    assert option["walkDistance"] == 20 and option["bikeDistance"] == 1000
    assert option["legs"][0]["stop"] == 1
    assert option["legs"][0]["segments"][-1]["path"][-1] == option["legs"][1]["path"][0]


def test_exact_marker_position_is_preserved_when_router_rounds_coordinates(router):
    _, locations, answer = router
    locations[A]["position"] = {"lat": 52.2305123, "lon": 21.0105123}
    raw = answer(START.position, A)
    raw["legs"][0]["to"]["lonlat"] = [21.01051, 52.23051]
    leg, = engine.legs_from_router(raw, from_name="Start", to_name="Stop")
    assert leg.end == (21.0105123, 52.2305123)


def _ride_leg(trip):
    calls = trip["calls"]
    return {"mode": "bus", "trip_id": trip["dep"]["trip_id"], "from": calls[0]["stop_id"], "to": calls[-1]["stop_id"]}


def _shapes(monkeypatch, sliced, by_stops):
    """Use the real _ride_path with fake GTFS shapes; returns the shape ids passed to shape_by_stops."""
    seen = []
    monkeypatch.setattr(geometry, "_ride_path", _RIDE_PATH)
    monkeypatch.setattr(geometry.mkuran, "trip_shape_id", lambda trip_id: "shape-" + trip_id)
    monkeypatch.setattr(geometry.mkuran, "shape_slice", lambda *args: sliced)
    monkeypatch.setattr(geometry.mkuran, "shape_by_stops", lambda shape_id, calls: seen.append(shape_id) or by_stops)
    return seen


def test_ride_without_stop_distances_uses_the_shape_projected_on_the_stops(router, monkeypatch):
    shape = [[52.25, 21.04], [52.255, 21.045], [52.26, 21.05]]
    seen = _shapes(monkeypatch, [], shape)
    trip = ride(line="wkd1")
    assert geometry.leg_path(_ride_leg(trip), calls=trip["calls"]) == (shape, False)
    assert seen == ["shape-wkd1"]


def test_ride_without_any_shape_is_kept_as_a_polyline_through_every_call(router, monkeypatch):
    _, locations, _ = router
    _shapes(monkeypatch, [], [])
    trip = ride(A, C)
    trip["calls"].insert(1, {**trip["calls"][0], "stop_id": B, "name": B, "dep": 29700, "arr": 29700})
    expected = [[locations[s]["position"]["lat"], locations[s]["position"]["lon"]] for s in (A, B, C)]
    # mapped positions, not the GTFS call coordinates
    assert geometry.leg_path(_ride_leg(trip), calls=trip["calls"]) == (expected, True)


@pytest.mark.parametrize("profile, steps, tag", [
    ("accessible", [], "bez schodów"),
    ("accessible", [[21.01, 52.23]], "bez schodów"),
    ("stroller", [], "bez schodów"),
    ("stroller", [[21.01, 52.23]], "schody tylko z rynnami"),
])
def test_step_free_tags_per_profile(router, profile, steps, tag):
    option = engine._option("walk", "Pieszo", [], NOW, 60)
    engine._street_tags(option, {"steps": steps, "elevators": []}, profile)
    assert option.tags == [tag]


def test_other_router_errors_are_not_hidden(router, monkeypatch):
    def failure(*args, **kwargs):
        raise street_router.RouteError(400, "bad mode")

    monkeypatch.setattr(street_router, "route", failure)
    with pytest.raises(street_router.RouteError, match="bad mode"):
        engine._street(START.position, A, "walk", "standard")


def test_disabled_bike_returns_422(router, monkeypatch):
    response = client(monkeypatch).post("/api/routes", json=request(travel="bike", bikeKmh=0).model_dump(by_alias=True))
    assert response.status_code == 422


def test_pushed_only_bike_totals_stay_correct_without_segments(router):
    _, _, answer = router
    raw = answer(START.position, END.position, "bike")
    raw["legs"][0].update(walk_m=510, bike_m=0)
    raw["legs"][0].pop("segments")
    legs = engine.legs_from_router(raw, from_name="Start", to_name="End")
    option = engine._option("bike", "Bike", legs, NOW)
    assert option.walkDistance == 510 and option.bikeDistance == 0
    assert option.model_dump()["bikeDistance"] == 0


