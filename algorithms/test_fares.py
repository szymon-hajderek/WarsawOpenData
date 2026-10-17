from fares import cheapest_fare, veturilo_pln

TIME = [
    {"price": 3.4, "duration_s": 1200, "transfers": None, "zones": {"1", "2", "1+2"}, "routes": {"175", "182"}},
    {"price": 4.4, "duration_s": 4500, "transfers": None, "zones": {"1"}, "routes": {"175", "182"}},
    {"price": 7.0, "duration_s": 5400, "transfers": None, "zones": {"1", "2", "1+2"}, "routes": {"175", "182"}},
    {"price": 15.0, "duration_s": 86400, "transfers": None, "zones": {"1"}, "routes": {"175", "182"}},
    {"price": 5.0, "duration_s": None, "transfers": 0, "zones": set(), "routes": {"L-1"}},
]


def test_short_ride_uses_the_20_minute_ticket():
    assert cheapest_fare(TIME, {"1"}, 600, {"175"}) == 3.4


def test_zone_1_ride_past_20_minutes_uses_the_75_minute_ticket():
    assert cheapest_fare(TIME, {"1"}, 1800, {"175"}) == 4.4


def test_zone_2_ride_past_20_minutes_uses_the_90_minute_ticket():
    assert cheapest_fare(TIME, {"1", "2"}, 1800, {"175"}) == 7.0


def test_local_line_is_charged_on_its_own_and_not_mixed_with_another_route():
    assert cheapest_fare(TIME, {"1"}, 600, {"L-1"}) == 5.0
    assert cheapest_fare(TIME, {"1"}, 600, {"L-1", "175"}) is None


def test_veturilo_standard_is_free_for_the_first_20_minutes():
    assert veturilo_pln(19, electric=False) == 0
    assert veturilo_pln(21, electric=False) == 1
    assert veturilo_pln(90, electric=False) == 4


def test_veturilo_electric_uses_its_own_brackets():
    assert veturilo_pln(19, electric=True) == 0
    assert veturilo_pln(30, electric=True) == 6
    assert veturilo_pln(61, electric=True) == 20
