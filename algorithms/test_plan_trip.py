from plan_trip import best_bike_pair, direct_rides, nearby, transfer_rides


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


def test_best_bike_pair_needs_a_bike_and_a_free_dock():
    stations = [
        {"id": "1", "lat": 0, "lon": 0, "bikes": 2, "docks": 0},
        {"id": "2", "lat": 1, "lon": 0, "bikes": 0, "docks": 3},
        {"id": "3", "lat": 0, "lon": 0.1, "bikes": 0, "docks": 0},
    ]
    pair = best_bike_pair((0, 0), (1, 0), stations, _distance, max_m=5000)
    assert pair[0]["id"] == "1"
    assert pair[1]["id"] == "2"
