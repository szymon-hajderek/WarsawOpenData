"""Walking totals and arrival times from street durations, without real data files."""
from datetime import datetime

import pytest

from app.models import Place
from app.routing import real_engine


@pytest.mark.parametrize("seconds, minutes, arrival", [
    (408.6, 7, "23:57"),
    (1268.5, 21, "00:11"),
])
def test_walk_total_and_arrival_include_the_walking_leg(monkeypatch, seconds, minutes, arrival):
    start = Place(id="start", label="Start", position=(52.2289, 21.0040))
    end = Place(id="end", label="End", position=(52.2318, 21.0060))
    departure = datetime.fromisoformat("2026-10-18T23:50:00+02:00")
    monkeypatch.setattr(real_engine, "_street", lambda *args: {
        "seconds": seconds,
        "legs": [{
            "mode": "walk", "seconds": seconds, "walk_m": 520.8, "bike_m": 0,
            "from": {"id": None, "lonlat": start.position[::-1]},
            "to": {"id": None, "lonlat": end.position[::-1]},
            "path": [start.position[::-1], end.position[::-1]],
        }],
    })

    option = real_engine.RealRouteEngine()._walk_option(
        start, end, start.position, end.position, "standard", departure,
    )

    assert option is not None
    assert option.legs[0].durationMin == minutes
    assert option.durationMin == minutes
    assert option.departure == "23:50"
    assert option.arrival == arrival
