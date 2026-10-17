from shape_units import shape_meters


def test_warsaw_kilometers_become_meters():
    assert shape_meters("2.399092") == 2399
    assert shape_meters(0.018596) == 19


def test_zero_stays_zero():
    assert shape_meters(0) == 0
    assert shape_meters("0") == 0


def test_values_already_in_meters_are_kept():
    assert shape_meters(1500) == 1500


def test_missing_distance_is_unknown():
    assert shape_meters(None) == -1
    assert shape_meters("") == -1
