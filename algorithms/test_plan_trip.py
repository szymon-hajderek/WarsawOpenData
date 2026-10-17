from datetime import datetime, timezone

from plan_trip import best_bike_pair, bike_access_pairs, direct_rides, nearby, service_moment, spread_groups, transfer_rides


def _distance(a, b):
    return abs(a[0] - b[0]) * 1000 + abs(a[1] - b[1]) * 1000


STOPS = [
    {"id": "a", "lat": 0, "lon": 0, "wheelchair": "1"},
    {"id": "b", "lat": 0.3, "lon": 0, "wheelchair": "2"},
    {"id": "c", "lat": 0.1, "lon": 0, "wheelchair": "0"},
]


def test_nearby_skips_a_stop_that_a_wheelchair_cannot_board():
    found = nearby((0, 0), STOPS, max_m=500, limit=5, distance=_distance, accessible=True)
    assert [s["id"] for s in found] == ["a", "c"]


def test_direct_ride_alights_at_the_destination_stop():
    def departures(stop_id, after):
        return [{"trip_id": "t1", "sec": 1000, "line": "175", "mode": "bus", "wheelchair": "1",
                 "route_id": "ztm:175"}]

    def onward(trip_id, stop_id, sec):
        return [
            {"stop_id": "a", "arr": 1000, "dep": 1000, "wheelchair": "1"},
            {"stop_id": "c", "arr": 1300, "dep": 1300, "wheelchair": "1"},
            {"stop_id": "d", "arr": 1600, "dep": 1600, "wheelchair": "1"},
        ]

    rides = direct_rides(["a"], {"d"}, departures, onward, accessible=False)
    assert len(rides) == 1
    assert rides[0]["calls"][-1]["stop_id"] == "d"
    assert rides[0]["dep"]["line"] == "175"


def test_transfer_changes_to_a_second_trip():
    def departures(stop_id, after):
        if stop_id == "a":
            return [{"trip_id": "t1", "sec": 1000, "wheelchair": "0"}]
        if after is not None and after >= 1200:
            return [{"trip_id": "t2", "sec": 1500, "wheelchair": "0"}]
        return []

    def onward(trip_id, stop_id, sec):
        if trip_id == "t1":
            return [
                {"stop_id": "a", "arr": 1000, "dep": 1000, "wheelchair": "0"},
                {"stop_id": "hub", "arr": 1200, "dep": 1200, "wheelchair": "0"},
            ]
        return [
            {"stop_id": "hub", "arr": 1500, "dep": 1500, "wheelchair": "0"},
            {"stop_id": "dest", "arr": 1800, "dep": 1800, "wheelchair": "0"},
        ]

    rides = transfer_rides(["a"], {"dest"}, departures, onward, {"hub": []}, accessible=False)
    assert len(rides) == 1
    assert rides[0]["second"]["dep"]["trip_id"] == "t2"
    assert rides[0]["walk_m"] == 0


def test_spread_groups_keeps_one_post_per_stop_group():
    posts = [
        {"id": "p1", "group": "centrum"},
        {"id": "p2", "group": "centrum"},
        {"id": "p3", "group": "politechnika"},
    ]
    assert [s["id"] for s in spread_groups(posts, 8)] == ["p1", "p3"]


def test_service_moment_rolls_the_clock_back_before_4am():
    assert service_moment(datetime(2026, 10, 18, 1, 30)) == ("20261017", 25 * 3600 + 30 * 60)
    assert service_moment(datetime(2026, 10, 18, 15, 0)) == ("20261018", 15 * 3600)
    # 23:30 UTC in October is 01:30 in Warsaw, still the previous service day.
    assert service_moment(datetime(2026, 10, 17, 23, 30, tzinfo=timezone.utc)) == (
        "20261017", 25 * 3600 + 30 * 60)


def test_best_bike_pair_skips_a_station_that_is_not_accepting_bikes():
    stations = [
        {"id": "1", "lat": 0, "lon": 0, "bikes": 2, "docks": 1, "renting": True},
        {"id": "2", "lat": 1, "lon": 0, "bikes": 0, "docks": 3, "returning": False},
        {"id": "3", "lat": 1, "lon": 0.1, "bikes": 0, "docks": 2, "returning": True},
    ]
    pair = best_bike_pair((0, 0), (1, 0), stations, _distance, max_m=5000)
    assert pair[1]["id"] == "3"


def test_bike_access_drops_the_bike_beside_a_stop_nearer_the_destination():
    stations = [
        {"id": "near", "lat": 0, "lon": 0, "bikes": 2, "docks": 0, "renting": True},
        {"id": "mid", "lat": 2, "lon": 0, "bikes": 0, "docks": 2, "returning": True},
    ]
    stops = [{"id": "stop", "lat": 2.1, "lon": 0}]
    pairs = bike_access_pairs((0, 0), (5, 0), stations, stops, _distance, max_m=5000, stop_m=500)
    assert pairs[0]["pickup"]["id"] == "near"
    assert pairs[0]["dropoff"]["id"] == "mid"
    assert pairs[0]["stop"]["id"] == "stop"


def test_best_bike_pair_needs_a_bike_and_a_free_dock():
    stations = [
        {"id": "1", "lat": 0, "lon": 0, "bikes": 2, "docks": 0},
        {"id": "2", "lat": 1, "lon": 0, "bikes": 0, "docks": 3},
        {"id": "3", "lat": 0, "lon": 0.1, "bikes": 0, "docks": 0},
    ]
    pair = best_bike_pair((0, 0), (1, 0), stations, _distance, max_m=5000)
    assert pair[0]["id"] == "1"
    assert pair[1]["id"] == "2"
