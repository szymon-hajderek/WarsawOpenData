"""Limits on POST /api/routes that do not need the timetable."""
from datetime import datetime
from zoneinfo import ZoneInfo

from bus_detect import _epoch
from sources.realtime import _collect

from app.models import Place, RouteRequest


def test_max_transfers_above_two_is_rejected():
    body = {
        "from": {"id": "a", "label": "A", "position": [52.2, 21.0]},
        "to": {"id": "b", "label": "B", "position": [52.3, 21.1]},
        "maxTransfers": 3,
    }
    try:
        RouteRequest.model_validate(body)
    except Exception:
        return
    raise AssertionError("maxTransfers 3 should be rejected")


def test_bike_kmh_zero_is_kept():
    req = RouteRequest.model_validate({
        "from": Place(id="a", label="A", position=(52.2, 21.0)),
        "to": Place(id="b", label="B", position=(52.3, 21.1)),
        "bikeKmh": 0,
        "excludedPoints": [{"position": [52.23, 21.01], "radiusM": 200}],
    })
    assert req.bikeKmh == 0
    assert req.excludedPoints[0].radiusM == 200
    assert req.maxTransfers is None


def test_feed_clock_is_warsaw_in_winter():
    got = _epoch("2026-01-15 12:00:00")
    expect = datetime(2026, 1, 15, 12, 0, tzinfo=ZoneInfo("Europe/Warsaw")).timestamp()
    assert got == expect


def test_plk_delay_minutes_become_seconds():
    out = {}
    _collect({"stationId": "123", "delayMinutes": 4, "name": "Warszawa"}, out)
    assert out["123"] == 240
