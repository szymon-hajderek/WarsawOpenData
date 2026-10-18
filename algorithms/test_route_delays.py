"""Run from backend/: uv run pytest ../algorithms"""
from route_delays import leg_vehicles, trip_ids_from_option

BUS = "ztm:2026-10-18:504:NdS:1:0519"
METRO = "ztm:2026-10-18:M1:NdS:3:0530"
TRAIN = "pkp:12345_6"


def test_split_keeps_dates_inside_ids():
    assert trip_ids_from_option(f"pt-{BUS}-{METRO}") == [BUS, METRO]
    assert trip_ids_from_option(f"pt-{BUS}-{TRAIN}") == [BUS, TRAIN]


def test_other_ids_give_nothing():
    assert trip_ids_from_option("walk") == []
    assert trip_ids_from_option("multi-0") == []
    assert trip_ids_from_option("pt-garbage") == []


TRIPS = {BUS: {"line": "504", "brigade": "1", "mode": "bus"}, METRO: {"line": "M1", "brigade": "3", "mode": "metro"}}


def test_bus_found_metro_not_live():
    rows = leg_vehicles([BUS, METRO], ["504", "M1"], TRIPS, {("504", "1"): "bus-1234"})
    assert rows[0]["vehicle_id"] == "bus-1234" and rows[0]["reason"] is None and rows[0]["transitIndex"] == 0
    assert rows[1]["reason"] == "not_live" and rows[1]["transitIndex"] == 1


def test_no_vehicle_and_unknown_trip():
    rows = leg_vehicles([BUS, "ztm:nope"], ["504", "17"], TRIPS, {})
    assert rows[0]["reason"] == "no_vehicle" and rows[1]["reason"] == "not_live"


def test_line_mismatch_is_skipped():
    assert leg_vehicles([BUS], ["180"], TRIPS, {("504", "1"): "bus-1234"}) == []
