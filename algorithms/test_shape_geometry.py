import pytest

from shape_geometry import slice_shape_by_stops


def test_keeps_track_bends_between_projected_stops():
    shape = [[52.2, 21], [52.2, 21.002], [52.202, 21.002]]
    stops = [[52.20001, 21.001], [52.201, 21.00201]]
    assert slice_shape_by_stops(shape, stops) == [
        [52.2, 21.001], [52.2, 21.002], [52.201, 21.002],
    ]


def test_follows_a_loop_in_stop_order_instead_of_cutting_across_it():
    shape = [[52.2, 21], [52.2, 21.002], [52.202, 21.002], [52.202, 21], [52.2, 21]]
    assert slice_shape_by_stops(shape, shape) == shape


def test_two_stops_on_one_segment_do_not_need_a_stop_to_stop_fallback():
    assert slice_shape_by_stops([[52.2, 21], [52.2, 21.004]], [[52.2, 21.001], [52.2, 21.003]]) == [
        [52.2, 21.001], [52.2, 21.003],
    ]


def test_duplicate_shape_vertices_are_harmless():
    assert slice_shape_by_stops([[52.2, 21], [52.2, 21], [52.2, 21.002]],
                               [[52.2, 21], [52.2, 21.002]]) == [[52.2, 21], [52.2, 21.002]]


@pytest.mark.parametrize("shape, stops", [([], []), ([[52.2, 21]], [[52.2, 21], [52.21, 21]]),
                                       ([[52.2, 21], [52.2, 21.002]], [[52.2, 21]])])
def test_missing_geometry_remains_unavailable(shape, stops):
    assert slice_shape_by_stops(shape, stops) == []
