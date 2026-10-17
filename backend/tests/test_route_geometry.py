"""Unavailable geometry must not turn into invented straight-line route legs."""
from datetime import datetime

import pytest

import street_router
from app.models import Place
from app.routing import real_engine

START = (52.2118727, 20.9822002)
END = (52.2319291, 21.006901)
PATH = [START, (52.212, 20.983), END]


@pytest.mark.parametrize("mode, profile", [("walk", "standard"), ("bike", "standard"), ("walk", "accessible")])
@pytest.mark.parametrize("status", [404, 422])
def test_no_street_path_drops_the_leg_instead_of_drawing_a_line(monkeypatch, mode, profile, status):
    def fail(*args, **kwargs):
        raise street_router.RouteError(status, "No usable street path")

    monkeypatch.setattr(street_router, "route", fail)
    assert real_engine._street(START, END, mode, profile) is None


@pytest.mark.parametrize("geometry", [[], [START]])
def test_empty_or_single_point_street_path_is_not_an_option(monkeypatch, geometry):
    monkeypatch.setattr(street_router, "route", lambda *a, **k: {
        "geometry": geometry, "seconds": 60, "length_m": 100,
    })
    assert real_engine._street(START, END, "walk", "standard") is None


def test_valid_street_geometry_is_preserved_and_unavailable_router_still_reports_failure(monkeypatch):
    raw = {"geometry": PATH, "seconds": 600, "length_m": 800}
    monkeypatch.setattr(street_router, "route", lambda *a, **k: raw)
    assert real_engine._street(START, END, "walk", "standard") == raw

    def down(*args, **kwargs):
        raise street_router.RouterUnavailable("Not running")

    monkeypatch.setattr(street_router, "route", down)
    with pytest.raises(street_router.RouterUnavailable):
        real_engine._street(START, END, "walk", "standard")


@pytest.mark.parametrize("mode", ["bus", "tram", "metro", "rail"])
@pytest.mark.parametrize("shape", [[], [START], PATH])
def test_transit_requires_a_real_gtfs_shape(monkeypatch, mode, shape):
    monkeypatch.setattr(real_engine.mkuran, "trip_shape_id", lambda _: "shape")
    monkeypatch.setattr(real_engine.mkuran, "shape_slice", lambda *a: shape)
    monkeypatch.setattr(real_engine, "_street", lambda *a: {
        "geometry": PATH, "seconds": 60, "length_m": 80,
    })
    monkeypatch.setattr(real_engine.alerts, "alerted_lines", lambda: [])
    engine = real_engine.RealRouteEngine()
    monkeypatch.setattr(engine, "_delay", lambda *a: 0)
    calls = [
        {"stop_id": "a", "name": "A", "lat": START[0], "lon": START[1], "shape_dist": 0, "dep": 29400},
        {"stop_id": "b", "name": "B", "lat": END[0], "lon": END[1], "shape_dist": 1000, "arr": 30000},
    ]
    ride = {"dep": {"trip_id": "trip", "mode": mode, "line": "1", "sec": 29400}, "calls": calls}
    frm = Place(id="start", label="Start", position=START)
    to = Place(id="end", label="End", position=END)
    option = engine._transit_option(
        frm, to, START, END, "standard", datetime(2026, 10, 18, 8), 28800, [ride], 0, None,
    )
    if len(shape) < 2:
        assert option is None
        assert real_engine._ride_path("trip", calls) == []
    else:
        assert option is not None
        assert option.legs[1].mode == mode
        assert option.legs[1].path == PATH
