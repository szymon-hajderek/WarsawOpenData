"""RouteRequest.excludeModes: sent to /plan, and the safety net on the options."""
import pytest
from pydantic import ValidationError

from app.models import RouteRequest
from app.routing import real_engine as engine

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


def test_plan_receives_min_bikes(plan):
    sent, _ = plan
    query(minBikes=3)
    assert sent[0]["min_bikes"] == 3
    query(minBikes=0)
    assert "min_bikes" not in sent[-1]
    query()
    assert "min_bikes" not in sent[-1]
    with pytest.raises(ValidationError):
        RouteRequest(from_=START, to=END, minBikes=-1)
