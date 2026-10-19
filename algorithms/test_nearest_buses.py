"""Run from backend/: uv run pytest ../algorithms"""
import math

from nearest_buses import haversine_m, rank_buses, track_mse

# About 111 m per 0.001 deg of latitude.
P = lambda lat, lon, t: {"lat": lat, "lon": lon, "t": t}


def test_single_point_is_squared_distance():
    d = haversine_m(52.23, 21.0, 52.231, 21.0)
    assert math.isclose(track_mse([P(52.23, 21.0, 0)], [P(52.231, 21.0, 0)]), d * d)


def test_pairs_by_closest_time():
    user = [P(52.23, 21.0, 0), P(52.231, 21.0, 10)]
    # The bus was where the user was, at the same times; the other entry is far but at an odd time.
    bus = [P(52.23, 21.0, 0), P(52.231, 21.0, 10), P(52.30, 21.0, 100)]
    assert track_mse(user, bus) == 0


def test_ranking_and_limit():
    user = [P(52.23, 21.0, 0)]
    history = {
        "far": [P(52.25, 21.0, 0)],
        "near": [P(52.2301, 21.0, 0)],
        "mid": [P(52.235, 21.0, 0)],
        "empty": [],
    }
    ranked = rank_buses(user, history, limit=2)
    assert [r["id"] for r in ranked] == ["near", "mid"]
    assert ranked[0]["rmse_m"] < 20


def test_track_beats_a_bus_that_only_passes_by():
    # The user moves north. Bus A moves with the user; bus B is now at the user's spot but came from the east.
    user = [P(52.230, 21.0, 0), P(52.231, 21.0, 10), P(52.232, 21.0, 20)]
    history = {
        "A": [P(52.230, 21.0, 0), P(52.231, 21.0, 10), P(52.2322, 21.0, 20)],
        "B": [P(52.232, 21.004, 0), P(52.232, 21.002, 10), P(52.232, 21.0, 20)],
    }
    assert rank_buses(user, history)[0]["id"] == "A"


def test_fewer_vehicles_than_limit_and_no_points():
    assert len(rank_buses([P(52.23, 21.0, 0)], {"x": [P(52.23, 21.0, 0)]}, limit=4)) == 1
    assert rank_buses([], {"x": [P(52.23, 21.0, 0)]}) == []


def test_vehicle_moved_to_the_phone_time():
    from nearest_buses import position_at, track_mse
    bus = [{"lat": 52.0, "lon": 21.0, "t": 0}, {"lat": 52.001, "lon": 21.0, "t": 10}]  # ~111 m north in 10 s
    assert position_at(bus, 5) == (52.0005, 21.0)  # between the points
    lat, _ = position_at(bus, 20)  # 10 s after the last feed point: moved on ~111 m
    assert abs(lat - 52.002) < 1e-9
    lat, _ = position_at(bus, 100)  # at most 30 s ahead
    assert abs(lat - 52.004) < 1e-9
    # a phone on board, ahead of the lagging feed, matches with ~0 error
    assert track_mse([{"lat": 52.002, "lon": 21.0, "t": 20}], bus) < 1.0
