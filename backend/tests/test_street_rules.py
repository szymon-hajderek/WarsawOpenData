"""Street-model rules that do not need data files."""
from sources import osm


def test_wheelchair_ramps_are_step_free_for_accessible_stroller_ramps_only_for_stroller():
    for mode in ("accessible", "stroller"):
        assert osm.step_free({"highway": "footway"}, mode)
        assert not osm.step_free({"highway": "steps"}, mode)
        assert not osm.step_free({"highway": "steps", "ramp": "yes"}, mode)  # often bicycle rails
        assert not osm.step_free({"highway": "steps", "ramp": "separate", "ramp:wheelchair": "separate"}, mode)
        assert osm.step_free({"highway": "steps", "ramp": "yes", "ramp:wheelchair": "yes"}, mode)
    # narrow stroller rails are not safe for a wheelchair
    assert not osm.step_free({"highway": "steps", "ramp:stroller": "yes"}, "accessible")
    assert osm.step_free({"highway": "steps", "ramp:stroller": "yes"}, "stroller")
