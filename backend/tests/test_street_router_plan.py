"""street_router.plan(): the service day and time sent to the router (no router needed)."""
from datetime import datetime, timezone

import street_router


def test_service_time_is_warsaw_local_and_night_belongs_to_the_previous_day():
    assert street_router.service_time(datetime(2026, 10, 21, 8, 30)) == ("20261021", 30600)
    assert street_router.service_time(datetime(2026, 10, 21, 0, 30)) == ("20261020", 86400 + 1800)
    assert street_router.service_time(datetime(2026, 10, 21, 4, 0)) == ("20261021", 14400)
    # an aware time is converted to Warsaw first (UTC+2 in October)
    assert street_router.service_time(datetime(2026, 10, 21, 6, 30, tzinfo=timezone.utc)) == ("20261021", 30600)


def test_plan_sends_the_service_time_and_returns_the_options(monkeypatch):
    sent = {}

    def fake_post(path, body):
        sent.update(path=path, body=body)
        return {"options": [{"seconds": 1.0}]}

    monkeypatch.setattr(street_router, "_post", fake_post)
    got = street_router.plan((52.23, 21.01), "ztm:701303", "accessible", when=datetime(2026, 10, 21, 0, 30),
                             max_legs=2)
    assert got == [{"seconds": 1.0}] and sent["path"] == "/plan"
    assert sent["body"] == {"from": [52.23, 21.01], "to": "ztm:701303", "mode": "accessible", "date": "20261020",
                            "time": 88200, "max_legs": 2}
