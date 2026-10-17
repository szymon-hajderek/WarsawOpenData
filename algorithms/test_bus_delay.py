"""Run from backend/: uv run pytest ../algorithms"""
from bus_delay import add_point, estimate, match_trip, pass_time, previous_stop, project, sched_at

M = 1 / 111195  # degrees of latitude per metre
LON = 21.0
P = lambda m, t: {"lat": 52.0 + m * M, "lon": LON, "t": t}  # a point `m` metres north of 52.0 N


def straight_shape(length_m=2000, step_m=100):
    d = list(range(0, length_m + 1, step_m))
    return (d, [52.0 + x * M for x in d], [LON] * len(d))


def trip(stop_m=(0, 500, 1000, 1500), start=1000.0, every_s=60, trip_id="t1", shape=None):
    stops = [{"id": f"s{i}", "name": f"Stop {i}", "lat": 52.0 + m * M, "lon": LON, "dist": m,
              "sched": start + i * every_s} for i, m in enumerate(stop_m)]
    return {"trip_id": trip_id, "headsign": "End", "start": start, "end": stops[-1]["sched"],
            "shape": shape or straight_shape(), "stops": stops}


def drive(speed=10.0, t0=1000.0, until=1200.0, every=10.0, start_m=0.0):
    """Feed points of a vehicle driving north at `speed` m/s."""
    t, out = t0, []
    while t <= until:
        out.append(P(start_m + (t - t0) * speed, t))
        t += every
    return out


def buffer_of(points, keep_s=600, broken_at=()):
    buf = []
    for i, p in enumerate(points):
        add_point(buf, p, i in broken_at, keep_s)
    return buf


# ---------------------------------------------------------------- buffer

def test_midpoint_between_feed_points():
    buf = buffer_of([P(0, 0), P(100, 10)])
    assert [p["mid"] for p in buf] == [False, True, False]
    assert buf[1]["t"] == 5 and abs(buf[1]["lat"] - (52.0 + 50 * M)) < 1e-9


def test_no_midpoint_after_failed_poll_or_long_gap():
    assert len(buffer_of([P(0, 0), P(100, 10)], broken_at={1})) == 2
    assert len(buffer_of([P(0, 0), P(100, 30)])) == 2  # 30 s > MAX_GAP_S


def test_same_time_is_ignored_and_old_points_dropped():
    buf = buffer_of([P(0, 0), P(0, 0), P(100, 10), P(200, 20)], keep_s=12)
    assert all(p["t"] >= 8 for p in buf) and buf[-1]["t"] == 20
    assert len(buffer_of([P(0, 0), P(0, 0)])) == 1


# ---------------------------------------------------------------- projection and stops

def test_project_on_straight_shape():
    along, off = project(straight_shape(), 52.0 + 750 * M, LON + 20 * M / 0.6157)
    assert abs(along - 750) < 1 and abs(off - 20) < 1


def test_project_too_far_is_none():
    assert project(straight_shape(), 52.0 + 500 * M, LON + 0.01) is None


def test_loop_uses_previous_projection():
    # out 0 -> 1000 m north, then back south along the same street: dist 1000 -> 2000
    d = list(range(0, 2001, 100))
    lat = [52.0 + (x if x <= 1000 else 2000 - x) * M for x in d]
    shape = (d, lat, [LON] * len(d))
    at = 52.0 + 300 * M  # 300 m on the way out = 1700 m on the way back
    assert abs(project(shape, at, LON, prev_dist=1650)[0] - 1700) < 1
    assert abs(project(shape, at, LON, prev_dist=250)[0] - 300) < 1


def test_previous_stop():
    stops = trip()["stops"]
    assert previous_stop(stops, 600) == 1
    assert previous_stop(stops, 500) == 1
    assert previous_stop(stops, -10) is None  # before the first stop
    assert previous_stop(stops, 1600) is None  # at / past the last stop


def test_pass_time_closest_within_radius():
    buf = buffer_of(drive())  # points every 50 m after densifying
    assert pass_time(buf, 52.0 + 500 * M, LON, 30) == 1050
    assert pass_time(buf, 52.0 + 525 * M, LON, 20) is None  # 25 m from the nearest point


def test_match_trip_by_time_window_and_shape():
    far = trip(trip_id="far", shape=([0, 1000], [52.1, 52.1 + 1000 * M], [LON, LON]))
    later = trip(trip_id="later", start=1000 + 3600)
    ok = trip(trip_id="ok")
    got, along = match_trip([far, later, ok], 52.0 + 300 * M, LON, now=1030)
    assert got["trip_id"] == "ok" and abs(along - 300) < 1
    assert match_trip([far, later], 52.0 + 300 * M, LON, now=1030) is None


def test_same_shape_trips_pick_the_one_scheduled_now():
    # the brigade drives the same shape at 1000 and at 1240 (stops every 60 s): at 300 m, now = 1270
    first, second = trip(trip_id="first"), trip(trip_id="second", start=1240)
    got, _ = match_trip([first, second], 52.0 + 300 * M, LON, now=1270)
    assert got["trip_id"] == "second"
    assert sched_at(first["stops"], 250) == 1030 and sched_at(first["stops"], -5) == 1000


# ---------------------------------------------------------------- delay

def test_on_time_late_and_early():
    # stop 1 at 500 m is scheduled at 1060; at 10 m/s from 0 m at t=1000 the vehicle passes it at 1050
    r = estimate(buffer_of(drive(until=1080)), [trip()], 30)
    assert r["available"] and r["prev_index"] == 1 and r["delay_s"] == -10
    late = estimate(buffer_of(drive(t0=1100, until=1180)), [trip()], 30)
    assert late["available"] and late["delay_s"] == 90


def test_unavailable_when_pass_not_in_buffer():
    # a failed poll right around the stop: feed points at 400 m and 600 m, no midpoint
    pts = [P(300, 1030), P(400, 1040), P(600, 1060), P(700, 1070)]
    r = estimate(buffer_of(pts, broken_at={2}), [trip()], 30)
    assert not r["available"] and r["reason"] == "no_pass_in_radius" and r["delay_s"] is None


def test_unavailable_reasons():
    assert estimate([], [trip()], 30)["reason"] == "no_trip"
    assert estimate(buffer_of([P(300, 99999)]), [trip()], 30)["reason"] == "no_trip"
    assert estimate(buffer_of([P(1800, 1300)]), [trip()], 30)["reason"] == "outside_trip"
