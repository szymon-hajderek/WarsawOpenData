"""Neighbouring walk legs (and own-bike legs) become one leg; nothing else changes. No network, no data files."""
from app.models import RouteLeg, RouteOption, RouteSegment
from app.routing.merge import merge_street_legs


def leg(mode="walk", frm="a", to="b", minutes=2, metres=100.0, path=None, **extra) -> RouteLeg:
    path = path or [(52.0, 21.0), (52.001, 21.001)]
    return RouteLeg.model_validate({"mode": mode, "from": frm, "to": to, "durationMin": minutes, "distanceM": metres, "path": path, **extra})


def test_two_walks_become_one_with_the_sums_and_both_ends():
    a = leg(frm="Stawki", to="Stawki", minutes=1, metres=28.8, path=[(52.0, 21.0), (52.0001, 21.0001)], fromId="ztm:1", toId="ztm:2")
    b = leg(frm="Stawki", to="B", minutes=3, metres=196.2, path=[(52.0001, 21.0001), (52.001, 21.001), (52.002, 21.002)], fromId="ztm:2", toId=None)
    [one] = merge_street_legs([a, b])
    assert (one.mode, one.from_, one.to) == ("walk", "Stawki", "B")
    assert (one.durationMin, one.distanceM) == (4, 225.0)
    assert (one.fromId, one.toId) == ("ztm:1", None)
    assert one.start == a.start and one.end == b.end


def test_the_path_keeps_every_point_and_the_shared_point_once():
    a = leg(path=[(52.0, 21.0), (52.0001, 21.0001)])
    b = leg(path=[(52.0001, 21.0001), (52.001, 21.001)])
    [one] = merge_street_legs([a, b])
    assert one.path == [(52.0, 21.0), (52.0001, 21.0001), (52.001, 21.001)]


def test_paths_that_do_not_meet_exactly_are_not_moved():
    a = leg(path=[(52.0, 21.0), (52.0001, 21.0001)])
    b = leg(path=[(52.00011, 21.00011), (52.001, 21.001)])
    [one] = merge_street_legs([a, b])
    assert one.path == [*a.path, *b.path]


def test_three_walks_in_a_row_are_one():
    legs = [leg(minutes=1, metres=10), leg(minutes=2, metres=20), leg(minutes=3, metres=30)]
    [one] = merge_street_legs(legs)
    assert (one.durationMin, one.distanceM) == (6, 60.0)


def test_a_ride_between_walks_keeps_them_apart():
    walk1, tram, walk2 = leg(), leg("tram", line="17"), leg()
    assert [l.mode for l in merge_street_legs([walk1, tram, walk2])] == ["walk", "tram", "walk"]


def test_only_the_trailing_walks_join_after_a_ride():
    out = merge_street_legs([leg(), leg("tram", line="17"), leg(minutes=1, metres=29), leg(minutes=3, metres=196)])
    assert [l.mode for l in out] == ["walk", "tram", "walk"]
    assert (out[2].durationMin, out[2].distanceM) == (4, 225.0)


def test_own_bike_legs_join_and_walk_next_to_bike_does_not():
    assert [l.mode for l in merge_street_legs([leg("bike"), leg("bike")])] == ["bike"]
    assert [l.mode for l in merge_street_legs([leg("walk"), leg("bike"), leg("walk")])] == ["walk", "bike", "walk"]


def test_rented_bikes_stay_apart():
    assert [l.mode for l in merge_street_legs([leg("veturilo"), leg("veturilo")])] == ["veturilo", "veturilo"]


def test_a_leg_that_ends_at_an_intermediate_stop_is_a_boundary():
    first = leg(stop=1)
    out = merge_street_legs([first, leg()])
    assert len(out) == 2 and out[0].stop == 1


def test_the_stop_number_of_the_last_part_goes_to_the_merged_leg():
    [one] = merge_street_legs([leg(), leg(stop=2)])
    assert one.stop == 2


def test_segments_elevators_and_steps_are_joined_in_order():
    sa = [RouteSegment(kind="walk", path=[(52.0, 21.0), (52.0001, 21.0001)], lengthM=10)]
    sb = [RouteSegment(kind="steps", path=[(52.0001, 21.0001), (52.001, 21.001)], lengthM=20)]
    a = leg(segments=sa, elevators=[(52.0, 21.0)])
    b = leg(segments=sb, steps=[(52.0005, 21.0005)])
    [one] = merge_street_legs([a, b])
    assert [s.kind for s in one.segments] == ["walk", "steps"]
    assert one.elevators == [(52.0, 21.0)] and one.steps == [(52.0005, 21.0005)]


def test_nothing_is_added_when_neither_leg_has_elevators_or_steps():
    [one] = merge_street_legs([leg(), leg()])
    assert one.elevators is None and one.steps is None


def test_the_option_totals_do_not_change():
    a = leg(minutes=1, metres=28.8)
    b = leg(minutes=3, metres=196.2)
    a._street_distances, b._street_distances = (28.8, 0.0), (196.2, 0.0)
    a._street_wait, b._street_wait = 5.0, 12.5

    def option(legs):
        return RouteOption(id="x", title="t", legs=legs, departure="10:00", arrival="10:04", durationMin=4,
                           distanceM=225.0, transfers=0, tags=[])

    before = option([a, b])
    after = option(merge_street_legs([a, b]))
    assert (after.walkDistance, after.bikeDistance, after.waitS) == (before.walkDistance, before.bikeDistance, before.waitS)
    assert after.walkDistance == 225.0 and after.waitS == 17.5


def test_the_input_legs_are_not_changed():
    a, b = leg(minutes=1), leg(minutes=3)
    merge_street_legs([a, b])
    assert (a.durationMin, b.durationMin) == (1, 3) and a.to == "b"
