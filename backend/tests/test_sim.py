"""Simulation clock and scenario logic that needs no data files."""
from datetime import datetime

import config
from sim import clock, scenario


def test_warsaw_epoch_ignores_the_server_zone():
    summer = datetime(2026, 10, 21, 8, 0)
    assert clock.warsaw_time(clock.warsaw_epoch(summer)) == summer
    assert clock.warsaw_epoch(summer) == 1792562400  # 06:00 UTC (CEST)
    assert clock.warsaw_epoch(datetime(2026, 11, 2, 8, 0)) == 1793602800  # 07:00 UTC (CET)


def test_clock_moves_only_when_simulated():
    try:
        clock.set_time(1000)
        clock.advance(5)
        assert clock.simulated() and clock.now() == 1005
    finally:
        clock.stop()
    assert not clock.simulated()


def test_cache_is_off_while_simulated():
    cache = config.TTLCache(ttl=1000)
    cache.put("k", 1)
    try:
        clock.set_time(0)
        assert cache.peek("k") is None
    finally:
        clock.stop()
    assert cache.peek("k") == 1


def test_recording_undoes_the_recorder_zone(tmp_path):
    # recorded on a UTC machine: vehicle t is the Warsaw wall time read as UTC, 2 h after the real poll
    poll = clock.warsaw_epoch(datetime(2026, 10, 17, 15, 23, 24))
    t = (datetime(2026, 10, 17, 15, 23, 4) - datetime(1970, 1, 1)).total_seconds()
    path = tmp_path / "rec.json"
    config.save_json(path, [{"poll": poll, "vehicles": [
        {"id": "bus-1000", "line": "161", "brigade": "2", "lat": 52.1, "lon": 21.2, "t": t}]}])
    row = scenario._recording(path)[0]["vehicles"][0]
    assert row["time"] == "2026-10-17 15:23:04"
    assert row["vehicle"] == "1000" and row["mode"] == "bus"
    assert poll - 30 < row["t"] < poll


def test_station_and_alert_changes_follow_the_clock():
    sc = scenario.Scenario({"source": "gtfs", "start": "2026-10-21T08:00:00",
                            "alerts": [{"from_s": 60, "lines": ["167"]}]}, "t")
    try:
        clock.set_time(sc.start)
        assert sc.alerted_lines() == set()
        clock.advance(60)
        assert sc.alerted_lines() == {"167"}
    finally:
        clock.stop()
