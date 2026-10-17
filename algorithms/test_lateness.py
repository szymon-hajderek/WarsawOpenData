from lateness import lateness_s


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


CALLS = [
    {"lat": 0, "lon": 0, "dep": 1000},
    {"lat": 10, "lon": 0, "dep": 1300},
    {"lat": 20, "lon": 0, "dep": 1600},
]


def test_a_vehicle_still_at_the_previous_stop_is_late():
    assert lateness_s(CALLS, (0, 0), now_sec=1500, distance=_distance) == 500


def test_a_vehicle_that_reached_the_scheduled_stop_is_on_time():
    assert lateness_s(CALLS, (10, 0), now_sec=1500, distance=_distance) == 0


def test_before_the_trip_starts_there_is_no_delay():
    assert lateness_s(CALLS, (0, 0), now_sec=500, distance=_distance) == 0
