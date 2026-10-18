"""Planner integration with the station overlay and router, without downloads or data files."""
from copy import deepcopy
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import street_router
from app.api import routes
from app.models import Place, RouteRequest
from app.routing import real_engine as engine

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
    monkeypatch.setattr(engine.stations, "locations", lambda: locations)
    engine._overlay.cache_clear()
    engine._FOOT_CACHE.clear()
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
    monkeypatch.setattr(engine, "_live_vehicles", lambda: [])
    monkeypatch.setattr(engine, "_trip_delays", lambda: {})
    monkeypatch.setattr(engine, "_station_delays", lambda: {})
    monkeypatch.setattr(engine.alerts, "alerted_lines", lambda: set())
    monkeypatch.setattr(engine, "_ride_path", lambda *args: [(52.25, 21.04), (52.26, 21.05)])
    yield calls, by_id, answer
    engine._overlay.cache_clear()
    engine._FOOT_CACHE.clear()


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


def test_mapped_candidates_calls_and_transit_ends_do_not_mutate_gtfs(router, monkeypatch):
    calls, locations, _ = router
    vertices = [{"id": key, "lat": loc["gtfs"]["lat"], "lon": loc["gtfs"]["lon"], "name": key}
                for key, loc in locations.items() if key in (A, B)]
    trip = ride()
    before = deepcopy((vertices, trip))
    monkeypatch.setattr(engine.mkuran, "vertices", lambda: vertices)
    monkeypatch.setattr(engine.mkuran, "departures", lambda station_id, *args, **kw: [trip["dep"]] if station_id == A else [])
    monkeypatch.setattr(engine.mkuran, "trip_onward", lambda *args: trip["calls"])
    monkeypatch.setattr(engine, "_footpaths", lambda *args: {})
    req = request(bikeKmh=0, maxTransfers=0)
    options = engine.RealRouteEngine().query_routes(START, END, req.profile, req.when, req)
    option = next(o for o in options if any(leg.mode == "bus" for leg in o.legs))
    walk_in, transit, walk_out = option.legs
    assert (walk_in.toId, transit.fromId, transit.toId, walk_out.fromId) == (A, A, B, B)
    assert walk_in.end == transit.start == tuple(locations[A]["position"].values())[::-1]
    assert transit.end == walk_out.start == tuple(locations[B]["position"].values())[::-1]
    assert walk_in.path[-1] == transit.start[::-1]
    assert transit.start != transit.path[0][::-1]  # GTFS shape is independent of the mapped marker.
    assert calls[0][0] == calls[1][0] == "access"
    assert (calls[0][3], calls[1][3]) == ("from", "to")
    assert (START.position, A, "walk") in [call[:3] for call in calls]
    assert (B, END.position, "walk") in [call[:3] for call in calls]
    assert (vertices, trip) == before


def test_transfer_uses_ids_and_joins_mapped_ends(router):
    calls, _, _ = router
    option = engine.RealRouteEngine()._transit_option(
        START, END, START.position, END.position, "standard", NOW, 28800,
        [ride(), ride(C, D, 30300, 30900, "17")], 0, None)
    assert option is not None
    assert (B, C, "walk") in [call[:3] for call in calls]
    for previous, following in zip(option.legs, option.legs[1:]):
        assert previous.end == following.start
        assert previous.toId == following.fromId


@pytest.mark.parametrize("start,end", [(START.position, END.position), (A, END.position), (START.position, B), (A, B)])
def test_veturilo_bridge_keeps_station_ids_and_ride_push_totals(router, start, end):
    calls, _, _ = router
    pickup, dropoff = {"id": P, "name": "Pickup"}, {"id": Q, "name": "Dropoff"}
    legs, seconds, _ = engine._bike_bridge(start, "Start", pickup, dropoff, end, "End", "standard")
    assert [call[:3] for call in calls] == [(start, P, "walk"), (P, Q, "bike"), (Q, end, "walk")]
    assert [leg.mode for leg in legs] == ["walk", "veturilo", "walk"]
    assert (legs[0].toId, legs[1].fromId, legs[1].toId, legs[2].fromId) == (P, P, Q, Q)
    option = engine._option("test", "Test", legs, NOW, seconds)
    assert option.walkDistance == 210 and option.bikeDistance == 500
    assert [segment.kind for segment in legs[1].segments] == ["push", "ride"]


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

    monkeypatch.setattr(engine.mkuran, "vertices", forbidden)
    monkeypatch.setattr(engine.stations, "locations", forbidden)
    monkeypatch.setattr(engine, "_live_vehicles", forbidden)
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
    assert engine._by_street(START.position, [{"id": A}], "accessible") == []
    req = request(travel="accessible")
    response = client(monkeypatch).post("/api/routes", json=req.model_dump(by_alias=True))
    assert response.status_code == status


@pytest.mark.parametrize("travel", ["walk", "accessible", "stroller", "bike", "transit"])
def test_router_downtime_returns_503(router, monkeypatch, travel):
    def unavailable(*args, **kwargs):
        raise street_router.RouterUnavailable("router stopped")

    monkeypatch.setattr(street_router, "route", unavailable)
    monkeypatch.setattr(street_router, "access", unavailable)
    monkeypatch.setattr(engine.mkuran, "vertices", lambda: [])
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


def test_veturilo_station_catalog_preserves_prefix_and_overlay_position(router, monkeypatch):
    _, locations, _ = router
    monkeypatch.setattr(engine.nextbike, "vehicle_types", lambda: [])
    monkeypatch.setattr(engine.nextbike, "status", lambda: [{"station_id": "P", "bikes": 2, "docks": 3}])
    monkeypatch.setattr(engine.nextbike, "stations", lambda **kw: [
        {"id": P, "station_id": "P", "name": "P", "lat": 52.25, "lon": 21.04}])
    station, = engine._stations()
    assert station["id"] == P
    assert (station["lat"], station["lon"]) == tuple(locations[P]["position"].values())


def test_exact_marker_position_is_preserved_when_router_rounds_coordinates(router):
    _, locations, answer = router
    locations[A]["position"] = {"lat": 52.2305123, "lon": 21.0105123}
    raw = answer(START.position, A)
    raw["legs"][0]["to"]["lonlat"] = [21.01051, 52.23051]
    leg, = engine.legs_from_router(raw, from_name="Start", to_name="Stop")
    assert leg.end == (21.0105123, 52.2305123)


def test_missing_transit_shape_drops_the_option(router, monkeypatch):
    monkeypatch.setattr(engine, "_ride_path", lambda *args: [])
    assert engine.RealRouteEngine()._transit_option(
        START, END, START.position, END.position, "standard", NOW, 28800, [ride()], 0, None) is None


def test_other_router_errors_are_not_hidden(router, monkeypatch):
    def failure(*args, **kwargs):
        raise street_router.RouteError(400, "bad mode")

    monkeypatch.setattr(street_router, "route", failure)
    with pytest.raises(street_router.RouteError, match="bad mode"):
        engine._street(START.position, A, "walk", "standard")


def test_disabled_bike_returns_422(router, monkeypatch):
    response = client(monkeypatch).post("/api/routes", json=request(travel="bike", bikeKmh=0).model_dump(by_alias=True))
    assert response.status_code == 422


def test_transfer_and_pathway_ids_are_canonicalized(router, monkeypatch):
    monkeypatch.setattr(engine.mkuran, "transfer_links", lambda: [
        ("outside-the-area", "old-B", 50), ("old-A", "old-B", 80)])
    monkeypatch.setattr(engine.mkuran, "pathway_links", lambda step_free: [("old-B", "old-A", 30, 70)])
    monkeypatch.setattr(engine.mkuran, "canonical", lambda station_id: {"old-A": A, "old-B": B}[station_id])
    links = engine._footpaths([
        {"id": A, "lat": 52.23, "lon": 21.01},
        {"id": B, "lat": 52.3, "lon": 21.1},
    ], 450)
    assert links[A] == [(B, 80, 80)] and links[B] == [(A, 30, 70)]


def test_pushed_only_bike_totals_stay_correct_without_segments(router):
    _, _, answer = router
    raw = answer(START.position, END.position, "bike")
    raw["legs"][0].update(walk_m=510, bike_m=0)
    raw["legs"][0].pop("segments")
    legs = engine.legs_from_router(raw, from_name="Start", to_name="End")
    option = engine._option("bike", "Bike", legs, NOW)
    assert option.walkDistance == 510 and option.bikeDistance == 0
    assert option.model_dump()["bikeDistance"] == 0


@pytest.mark.parametrize("placement", ["before", "after", "middle"])
def test_bike_transit_variants_pass_transit_stop_ids_to_the_bridge(router, monkeypatch, placement):
    calls, locations, _ = router
    pickup, dropoff = [
        {"id": station_id, "name": station_id, "lat": locations[station_id]["position"]["lat"],
         "lon": locations[station_id]["position"]["lon"], "bikes": 2, "docks": 2}
        for station_id in (P, Q)]
    monkeypatch.setattr(engine, "_stations", lambda: [pickup, dropoff])
    planner = engine.RealRouteEngine()
    if placement == "middle":
        monkeypatch.setattr(engine, "bike_between", lambda *args: {
            "first": ride(), "second": ride(C, D, 30300, 30900, "17"),
            "pickup": pickup, "dropoff": dropoff,
        })
        option = planner._bike_in_the_middle(
            START, END, START.position, END.position, "standard", NOW, 28800,
            [], {D}, [A], None, None, False)
        expected = [(B, P, "walk"), (Q, C, "walk")]
    else:
        pairs = [{"stop": {"id": A}, "pickup": pickup, "dropoff": dropoff}] if placement == "before" else []
        monkeypatch.setattr(engine, "bike_access_pairs", lambda *args: pairs)
        monkeypatch.setattr(engine, "direct_rides", lambda *args: [ride()])
        monkeypatch.setattr(engine, "best_bike_pair", lambda *args, **kwargs: (pickup, dropoff))
        # For the after variant the raw call position is far enough to consider bike egress.
        options = planner._bike_with_transit(
            START, END, START.position, END.position, "standard", NOW, 28800,
            [], {B}, [ride()] if placement == "after" else [], None, None, False)
        option, = options
        expected = [(Q, A, "walk")] if placement == "before" else [(B, P, "walk")]
    assert option is not None
    assert any(leg.mode == "veturilo" for leg in option.legs)
    for call in expected:
        assert call in [item[:3] for item in calls]
    for previous, following in zip(option.legs, option.legs[1:]):
        assert previous.end == following.start and previous.toId == following.fromId
