from fares import brackets_for, cheapest_fare, open_fare, veturilo_from_brackets, veturilo_pln

TIME = [
    {"price": 3.4, "duration_s": 1200, "transfers": None, "zones": {"1", "2", "1+2"}, "routes": {"175", "182"}},
    {"price": 4.4, "duration_s": 4500, "transfers": None, "zones": {"1"}, "routes": {"175", "182"}},
    {"price": 7.0, "duration_s": 5400, "transfers": None, "zones": {"1", "2", "1+2"}, "routes": {"175", "182"}},
    {"price": 15.0, "duration_s": 86400, "transfers": None, "zones": {"1"}, "routes": {"175", "182"}},
    {"price": 5.0, "duration_s": None, "transfers": 0, "zones": set(), "routes": {"L-1"}},
]


def test_open_fare_picks_the_cheapest_ticket_that_covers_the_ride():
    wkd = [
        {"price": 4.1, "duration_s": 1140, "zones": set(), "routes": set()},
        {"price": 6.3, "duration_s": 2280, "zones": set(), "routes": set()},
        {"price": 9.2, "duration_s": None, "zones": set(), "routes": set()},
    ]
    assert open_fare(wkd, 600) == 4.1
    assert open_fare(wkd, 2000) == 6.3
    assert open_fare(wkd, 9000) == 9.2


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


STANDARD = [
    {"start": 20, "interval": 0, "rate": 1, "end": 60},
    {"start": 60, "interval": 0, "rate": 3, "end": 120},
    {"start": 120, "interval": 0, "rate": 5, "end": 180},
    {"start": 180, "interval": 60, "rate": 7, "end": 720},
    {"start": 720, "interval": 0, "rate": 200},
]
ELECTRIC = [
    {"start": 20, "interval": 0, "rate": 6, "end": 60},
    {"start": 60, "interval": 60, "rate": 14, "end": 720},
    {"start": 720, "interval": 0, "rate": 300},
]


def test_gbfs_brackets_match_the_plan_names():
    assert veturilo_from_brackets(19, STANDARD) == 0
    assert veturilo_from_brackets(21, STANDARD) == 1
    assert veturilo_from_brackets(90, STANDARD) == 4
    assert veturilo_from_brackets(721, STANDARD) == 272
    assert veturilo_from_brackets(30, ELECTRIC) == 6
    assert veturilo_from_brackets(61, ELECTRIC) == 20


def test_brackets_for_picks_the_standard_and_the_ebike_plan():
    plans = [{"plan_id": "a", "per_min_pricing": STANDARD}, {"plan_id": "b", "per_min_pricing": ELECTRIC}]
    assert brackets_for(plans, electric=False) == STANDARD
    assert brackets_for(plans, electric=True) == ELECTRIC
