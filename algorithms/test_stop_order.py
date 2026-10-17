"""Run from the repo root or `backend/`: `pytest ../algorithms`."""
import pytest

from stop_order import MAX_STOPS, best_order, path_length, travel_seconds


def d(a: float, b: float) -> float:
    """Distance on a line."""
    return abs(a - b)


def test_time_order_can_differ_from_straight_line_order():
    # Three slow walks (600 m) cost more than one transit hop that backtracks,
    # so the time order is not the shortest path in metres.
    def metres(a, b):
        return abs(a - b)

    by_distance = best_order(0, [600, 1300], 2000, metres)
    by_time = best_order(0, [600, 1300], 2000, lambda a, b: travel_seconds(metres(a, b)))
    assert by_distance == [600, 1300]
    assert by_time == [1300, 600]


def test_no_or_one_stop_is_unchanged():
    assert best_order(0, [], 10, d) == []
    assert best_order(0, [7], 10, d) == [7]


def test_reorders_stops_along_a_line():
    # start 0, end 10, stops given zig-zag: the shortest path visits them in increasing order
    assert best_order(0, [8, 2, 5], 10, d) == [2, 5, 8]


def test_start_and_end_stay_fixed_so_a_stop_behind_the_start_is_visited_first():
    # a stop at -5 behind the start must still be visited between start and end
    order = best_order(0, [-5, 6], 10, d)
    assert order == [-5, 6]
    assert path_length([0, *order, 10], d) == 5 + 11 + 4


def test_ties_keep_the_given_order():
    # the same distance either way: the given order wins
    assert best_order(0, [3, -3], 0, d) == [3, -3]
    assert best_order(0, [-3, 3], 0, d) == [-3, 3]


def test_is_never_worse_than_the_given_order():
    stops = [9, 1, 7, 3, 5]
    given = path_length([0, *stops, 10], d)
    best = path_length([0, *best_order(0, stops, 10, d), 10], d)
    assert best <= given


def test_two_dimensional_points():
    def euclid(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    order = best_order((0, 0), [(10, 10), (1, 1), (5, 5)], (12, 12), euclid)
    assert order == [(1, 1), (5, 5), (10, 10)]


def test_too_many_stops_is_rejected():
    with pytest.raises(ValueError):
        best_order(0, list(range(MAX_STOPS + 1)), 100, d)
