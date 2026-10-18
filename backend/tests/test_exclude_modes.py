"""RouteRequest.excludeModes: sent to /plan, applied in the Python fallback, and the safety net on the options."""
import numpy as np
import pytest
from pydantic import ValidationError

import street_router
from app.models import RouteRequest
from app.routing import real_engine as engine
from sources import mkuran

from test_plan_engine import BUS, TRANSFER, VETURILO, WALK, plan  # noqa: F401  (plan = fixture)
from test_station_routes import END, START, request, router  # noqa: F401  (router = fixture)


def query(**options):
    return engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                                 search=request(**options))


def test_unknown_mode_is_rejected_and_default_is_empty():
    assert RouteRequest(from_=START, to=END).excludeModes == []
    with pytest.raises(ValidationError):
        RouteRequest(from_=START, to=END, excludeModes=["ferry"])


def test_plan_receives_exclude_modes(plan):
    sent, _ = plan
    query(excludeModes=["tram", "bus"])
    assert sent[0]["exclude_modes"] == ["bus", "tram"] and "veturilo_s" not in sent[0]
    query()
    assert "exclude_modes" not in sent[-1]


def test_excluding_veturilo_also_turns_rentals_off(plan):
    sent, _ = plan
    query(excludeModes=["veturilo"])
    assert sent[0]["exclude_modes"] == ["veturilo"] and sent[0]["veturilo_s"] == 0


def test_safety_net_drops_options_with_an_excluded_leg(plan):
    _, answers = plan
    answers[0] = [WALK, BUS, VETURILO, TRANSFER]
    ids = {o.id for o in query(excludeModes=["metro", "veturilo"])}
    assert ids == {"walk", "pt-ztm:T1"}  # the router ignored the key here: the metro / Veturilo options go


def test_own_bike_is_not_excluded_by_veturilo(router):
    options = engine.RealRouteEngine().query_routes(START, END, "standard", when="2026-10-18T08:00",
                                                    search=request(travel="bike", excludeModes=["veturilo"]))
    assert [leg.mode for leg in options[0].legs] == ["bike"]


def test_fallback_passes_exclude_modes_to_departures(router, monkeypatch):
    seen = []
    monkeypatch.setattr(engine.mkuran, "departures",
                        lambda stop_id, *args, **kw: seen.append(kw.get("exclude_modes")) or [])
    monkeypatch.setattr(engine, "_stations", lambda: [])
    query(excludeModes=["rail"])
    assert seen and all(value == frozenset({"rail"}) for value in seen)


def test_departures_skip_excluded_modes_before_the_limit(monkeypatch):
    # trips 0 (bus), 1 (trolleybus = bus), 2 (tram), all from stop S on the service day
    monkeypatch.setattr(mkuran, "stop_times", lambda: {"trip": np.array([0, 1, 2]), "dep": np.array([100, 200, 300])})
    monkeypatch.setattr(mkuran, "trips", lambda: [("t0", "r0", "s", "b"), ("t1", "r1", "s", "b"), ("t2", "r2", "s", "b")])
    monkeypatch.setattr(mkuran, "routes", lambda: {
        "r0": {"short_name": "175", "mode": "bus", "feed": "ztm"},
        "r1": {"short_name": "T1", "mode": "trolleybus", "feed": "ztm"},
        "r2": {"short_name": "9", "mode": "tram", "feed": "ztm"}})
    monkeypatch.setattr(mkuran, "services", lambda: {"s": {"20261018"}})
    monkeypatch.setattr(mkuran, "stops_by_id", lambda: {"S": {}})
    monkeypatch.setattr(mkuran, "_targets", lambda stop_id: [0])
    monkeypatch.setattr(mkuran, "_rows_by_stop", lambda: {0: np.array([0, 1, 2])})
    monkeypatch.setattr(mkuran, "frequencies", lambda: {})
    monkeypatch.setattr(mkuran, "_trip_bounds", lambda: None)
    assert [d["line"] for d in mkuran.departures("S", "20261018", 0, limit=1, exclude_modes={"bus"})] == ["9"]
    assert [d["line"] for d in mkuran.departures("S", "20261018", 0)] == ["175", "T1", "9"]
