import pytest

from journey_points import nearest_anchor


def test_chooses_closest_catalog_object_without_rounding_or_cutoff():
    anchors = [("ztm:1", 52.2, 21.0), ("vet:2", 52.200123456, 21.000123456)]
    assert nearest_anchor((52.20013, 21.00013), anchors) == anchors[1]
    assert nearest_anchor((53.0, 22.0), anchors) in anchors


def test_geographic_distance_accounts_for_longitude_and_breaks_ties_by_id():
    assert nearest_anchor((60, 0), [("north", 60.01, 0), ("east", 60, 0.01)])[0] == "east"
    assert nearest_anchor((52, 21), [("z", 52, 21), ("a", 52, 21)])[0] == "a"
    with pytest.raises(ValueError):
        nearest_anchor((52, 21), [])
