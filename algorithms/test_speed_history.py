"""Run from the repo root or `backend/`: `pytest ../algorithms`."""
import pytest

from speed_history import split_track, summarize

M_PER_DEG_LAT = 111_195.0  # metres per degree of latitude (haversine, r = 6371 km)


def track(parts, start_t=0.0, step_s=5.0):
    """A straight north-going track. `parts`: (metres, km/h) segments; km/h 0 = standing still."""
    pts = [{"lat": 52.0, "lon": 21.0, "t": start_t}]
    lat, t = 52.0, start_t
    for metres, kmh in parts:
        if kmh == 0:
            for _ in range(int(metres)):  # `metres` seconds of standing still
                t += step_s
                pts.append({"lat": lat, "lon": 21.0, "t": t})
            continue
        speed = kmh / 3.6
        walked = 0.0
        while walked < metres - 1e-6:
            d = min(speed * step_s, metres - walked)
            walked += d
            lat += d / M_PER_DEG_LAT
            t += d / speed
            pts.append({"lat": lat, "lon": 21.0, "t": t})
    return pts


def one(records, mode):
    found = [r for r in records if r["mode"] == mode]
    assert len(found) == 1, records
    return found[0]


def test_clean_walk_gives_its_speed():
    records = split_track(track([(1000, 5)]), [{"mode": "walk", "distanceM": 1000}], at="2026-10-01")
    r = one(records, "walking")
    assert r["kmh"] == pytest.approx(5.0, abs=0.1)
    assert r["distanceM"] == pytest.approx(1000, abs=5)
    assert r["at"] == "2026-10-01"


def test_standing_still_is_not_counted():
    parts = [(500, 5), (36, 0), (500, 5)]  # 36 x 5 s = 3 minutes of standing
    r = one(split_track(track(parts), [{"mode": "walk", "distanceM": 1000}]), "walking")
    assert r["kmh"] == pytest.approx(5.0, abs=0.1)


def test_walk_can_count_as_wheelchair():
    records = split_track(track([(800, 3.6)]), [{"mode": "walk", "distanceM": 800}], walk_as="wheelchair")
    assert one(records, "wheelchair")["kmh"] == pytest.approx(3.6, abs=0.1)
    assert not [r for r in records if r["mode"] == "walking"]


def test_walk_and_bike_legs_are_split_by_planned_distance():
    legs = [{"mode": "walk", "distanceM": 500}, {"mode": "bike", "distanceM": 2000}]
    records = split_track(track([(500, 5), (2000, 15)]), legs)
    assert one(records, "walking")["kmh"] == pytest.approx(5.0, abs=0.2)
    assert one(records, "cycling")["kmh"] == pytest.approx(15.0, abs=0.2)


def test_public_transport_legs_only_take_their_share():
    legs = [{"mode": "walk", "distanceM": 600}, {"mode": "metro", "distanceM": 5000}, {"mode": "walk", "distanceM": 600}]
    records = split_track(track([(600, 5), (5000, 35), (600, 5)]), legs)
    walking = one(records, "walking")  # both walking legs are one record
    assert walking["kmh"] == pytest.approx(5.0, abs=0.2)
    assert walking["distanceM"] == pytest.approx(1200, abs=30)


def test_too_short_a_leg_makes_no_record():
    assert split_track(track([(100, 5)]), [{"mode": "walk", "distanceM": 100}]) == []


def test_implausible_speed_is_rejected():
    # 25 km/h "walking" is a car or a bike, not a walk
    assert split_track(track([(1000, 25)]), [{"mode": "walk", "distanceM": 1000}]) == []


def test_a_gps_jump_is_ignored():
    pts = track([(500, 5)])
    jump = {"lat": pts[-1]["lat"] + 1000 / M_PER_DEG_LAT, "lon": 21.0, "t": pts[-1]["t"] + 1}  # 1 km in 1 s
    pts.append(jump)
    pts.extend(track([(500, 5)], start_t=jump["t"] + 5)[1:])
    for p in pts[pts.index(jump) + 1:]:
        p["lat"] += 1000 / M_PER_DEG_LAT
    r = one(split_track(pts, [{"mode": "walk", "distanceM": 1000}]), "walking")
    assert r["kmh"] == pytest.approx(5.0, abs=0.2)


def test_a_track_that_does_not_match_the_plan_is_ignored():
    assert split_track(track([(800, 5)]), [{"mode": "walk", "distanceM": 5000}]) == []
    assert split_track([], [{"mode": "walk", "distanceM": 500}]) == []


def test_bad_walk_as_is_rejected():
    with pytest.raises(ValueError):
        split_track(track([(500, 5)]), [{"mode": "walk", "distanceM": 500}], walk_as="car")


def rec(mode, kmh, at, distance=1000):
    return {"mode": mode, "distanceM": distance, "durationS": round(distance / (kmh / 3.6)), "kmh": kmh, "at": at}


def test_summary_needs_enough_trips():
    records = [rec("walking", 5, f"2026-10-0{i}") for i in range(1, 5)]
    s = summarize(records)["walking"]
    assert s["trips"] == 4 and s["enough"] is False
    assert s["avgKmh"] == pytest.approx(5.0, abs=0.1)


def test_summary_average_and_enough():
    records = [rec("walking", k, f"2026-10-0{i + 1}") for i, k in enumerate([4.8, 5.0, 5.2, 5.4, 5.6])]
    s = summarize(records)["walking"]
    assert s["enough"] is True and s["trips"] == 5
    assert s["avgKmh"] == pytest.approx(5.2, abs=0.1)
    assert s["medianKmh"] == pytest.approx(5.2, abs=0.01)
    assert s["distanceKm"] == pytest.approx(5.0, abs=0.01)


def test_outliers_are_ignored():
    records = [rec("walking", 5, f"2026-10-0{i}") for i in range(1, 6)] + [rec("walking", 9.9, "2026-10-07")]
    assert summarize(records)["walking"]["avgKmh"] == pytest.approx(5.0, abs=0.1)


def test_only_the_latest_trips_count():
    old = [rec("cycling", 8, f"2026-01-{i:02d}") for i in range(1, 11)]
    new = [rec("cycling", 16, f"2026-10-{i:02d}") for i in range(1, 6)]
    s = summarize(old + new, window=5)["cycling"]
    assert s["trips"] == 5 and s["avgKmh"] == pytest.approx(16.0, abs=0.1)


def test_modes_are_separate_and_always_present():
    s = summarize([rec("walking", 5, "2026-10-01")])
    assert set(s) == {"walking", "cycling", "wheelchair"}
    assert s["cycling"] == {"trips": 0, "distanceKm": 0.0, "avgKmh": None, "medianKmh": None, "enough": False}


def test_a_veturilo_leg_counts_as_cycling():
    legs = [{"mode": "walk", "distanceM": 500}, {"mode": "veturilo", "distanceM": 2000}]
    records = split_track(track([(500, 5), (2000, 15)]), legs)
    assert one(records, "cycling")["kmh"] == pytest.approx(15.0, abs=0.2)
