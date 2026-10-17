from calories import net_kcal


def test_walking_burns_more_than_resting():
    legs = [{"mode": "walk", "distanceM": 1000}]
    assert net_kcal(legs, walk_kmh=4.8, bike_kmh=13) > 0


def test_an_electric_wheelchair_adds_no_calories_on_a_walk():
    legs = [{"mode": "walk", "distanceM": 1000}, {"mode": "bus", "distanceM": 3000}]
    assert net_kcal(legs, 4.0, 13, wheelchair="electric") == 0


def test_a_heavier_body_burns_more():
    legs = [{"mode": "bike", "distanceM": 5000}]
    light = net_kcal(legs, 4.8, 16, {"weightKg": 50, "heightCm": 165, "age": 30, "sex": "female"})
    heavy = net_kcal(legs, 4.8, 16, {"weightKg": 110, "heightCm": 190, "age": 40, "sex": "male"})
    assert heavy > light


def test_a_veturilo_leg_counts_like_an_own_bike():
    own = net_kcal([{"mode": "bike", "distanceM": 5000}], 4.8, 16)
    rented = net_kcal([{"mode": "veturilo", "distanceM": 5000}], 4.8, 16)
    assert rented == own > 0


def test_a_leg_with_a_time_uses_its_own_speed():
    # 5 km in 15 minutes is 20 km/h, not the 12 km/h of the pace given
    fast = net_kcal([{"mode": "veturilo", "distanceM": 5000, "durationMin": 15}], 4.8, 12)
    slow = net_kcal([{"mode": "veturilo", "distanceM": 5000}], 4.8, 12)
    assert fast > 0 and slow > 0 and fast != slow
