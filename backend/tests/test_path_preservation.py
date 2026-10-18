"""Repair geometry without dropping routes, moving places, or changing fallback behavior."""
from datetime import datetime

import numpy as np
import pytest

import street_router
from app.models import Place
from app.routing import real_engine

START = (52.2, 21.0)
END = (52.201, 21.001)
PATH = [START, (52.2, 21.001), END]


@pytest.mark.parametrize("mode", ["bus", "tram", "metro", "rail"])
@pytest.mark.parametrize("has_shape", [True, False])
@pytest.mark.parametrize("has_distances", [True, False])
def test_transit_curves_and_route_availability_are_preserved(monkeypatch, mode, has_shape, has_distances):
    monkeypatch.setattr(real_engine.mkuran, "trip_shape_id", lambda _: "shape")
    # Exercise real shape slicing, including a bend that is absent from the stop coordinates.
    monkeypatch.setattr(real_engine.mkuran, "_shapes", lambda: {
        "shape": (np.array([0, 100, 200]), np.array([p[0] for p in PATH]), np.array([p[1] for p in PATH])),
    } if has_shape else {})
    monkeypatch.setattr(real_engine, "_street", lambda *a: {
        "geometry": PATH, "seconds": 60, "length_m": 80,
    })
    monkeypatch.setattr(real_engine.alerts, "alerted_lines", lambda: [])
    engine = real_engine.RealRouteEngine()
    monkeypatch.setattr(engine, "_delay", lambda *a: 0)
    calls = [
        {"stop_id": "a", "name": "A", "lat": START[0], "lon": START[1], "shape_dist": 0, "dep": 29400},
        {"stop_id": "b", "name": "B", "lat": END[0], "lon": END[1], "shape_dist": 200, "arr": 30000},
    ]
    if not has_distances:
        for call in calls:
            call["shape_dist"] = -1
    ride = {"dep": {"trip_id": "trip", "mode": mode, "line": "1", "sec": 29400}, "calls": calls}
    frm = Place(id="start", label="Start", position=START)
    to = Place(id="end", label="End", position=END)
    option = engine._transit_option(
        frm, to, START, END, "standard", datetime(2026, 10, 18, 8), 28800, [ride], 0, None,
    )
    assert option is not None
    assert option.legs[1].mode == mode
    assert option.legs[1].path == (PATH if has_shape else [START, END])
    assert (frm.position, to.position) == (START, END)


def test_map_geometry_does_not_change_street_costs_or_selected_coordinates(monkeypatch):
    network = [(52.2, 21.0001), (52.2008, 21.0001), (52.2008, 21.001)]
    raw = {"geometry": [START, *network, END], "network_geometry": network, "seconds": 600, "length_m": 800}
    monkeypatch.setattr(street_router, "route", lambda *a, **k: raw)
    street = real_engine._street(START, END, "walk", "standard")
    leg = real_engine._leg("walk", "A", "B", None, street)
    assert leg.path == raw["geometry"]
    assert leg.networkPath == network
    assert leg.durationMin == 10 and leg.distanceM == 800
    assert leg.start == (START[1], START[0]) and leg.end == (END[1], END[0])


def test_cpp_geometry_exposes_only_graph_vertices_for_drawing(monkeypatch):
    graph = [[21.0001, 52.2], [21.0001, 52.2008], [21.001, 52.2008]]
    full = [[START[1], START[0]], *graph, [END[1], END[0]]]
    monkeypatch.setattr(street_router, "_post", lambda *a: {"walk_m": 800, "bike_m": 0, "path": full})
    answer = street_router.route(START, END)
    assert answer["path"] == full
    assert answer["network_geometry"] == [[lat, lon] for lon, lat in graph]
    assert answer["geometry"] == [[lat, lon] for lon, lat in full]


@pytest.mark.parametrize("mode, profile", [("walk", "standard"), ("bike", "standard"), ("walk", "accessible")])
def test_successful_street_paths_are_kept_with_every_vertex(monkeypatch, mode, profile):
    raw = {"geometry": PATH, "seconds": 600, "length_m": 800}
    monkeypatch.setattr(street_router, "route", lambda *a, **k: raw)
    assert real_engine._street(START, END, mode, profile) == raw


@pytest.mark.parametrize("mode", ["walk", "bike"])
def test_existing_street_failure_fallback_is_not_removed(monkeypatch, mode):
    def fail(*args, **kwargs):
        raise street_router.RouteError(404, "No path")

    monkeypatch.setattr(street_router, "route", fail)
    leg = real_engine._street(START, END, mode, "standard")
    assert leg is not None
    assert leg["geometry"] == [list(START), list(END)]
