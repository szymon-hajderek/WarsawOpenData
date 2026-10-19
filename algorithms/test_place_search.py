import json
from pathlib import Path

import pytest

from place_search import fold, group_by_name, looks_like_address, match_score, prepare, search, words

LANDMARKS = Path(__file__).resolve().parent.parent / "data" / "places" / "landmarks.json"


def test_fold_removes_accents_and_case():
    assert fold("  Łódź-Kaliska  ") == "lodz kaliska"
    assert fold("Marszałkowska") == "marszalkowska"


def test_words_split_letters_digits_and_punctuation():
    assert words("DS2 UW") == ["ds", "2", "uw"]
    assert words("Os.Ługi") == ["os", "lugi"]
    assert words('Dom Studenta "Żwirek"') == ["dom", "studenta", "zwirek"]


def test_match_quality_order():
    assert match_score("Centrum", "Centrum") == 0
    assert match_score("cent", "Centrum") == 1
    assert match_score("metro pol", "Metro Politechnika") == 1
    assert match_score("politechnika metro", "Metro Politechnika") == 2
    assert match_score("politechn", "Metro Politechnika") == 3
    assert match_score("echni", "Metro Politechnika") == 4
    assert match_score("xyz", "Metro Politechnika") is None
    assert match_score("", "Centrum") is None


def test_abbreviations_match_both_ways():
    assert match_score("plac zbawiciela", "Pl. Zbawiciela") == 1
    assert match_score("pl. zbawiciela", "Plac Zbawiciela") == 1
    assert match_score("pl. zbawiciela", "Pl. Zbawiciela") == 0
    assert match_score("dworzec centralny", "Dw. Centralny") == 1
    assert match_score("dom studenta riviera", "DS Riviera") == 1
    assert match_score("ds riviera", "Dom Studenta Riviera") == 1
    assert match_score("osiedle kabaty", "Os. Kabaty") == 1
    assert match_score("aleje jerozolimskie", "Al. Jerozolimskie") == 2
    assert match_score("uniwersytet warszawski", "Kampus Ochota UW") == 2
    assert match_score("pw", "Gmach Główny Politechniki Warszawskiej") == 2


def test_numbers_are_whole_tokens_and_nr_is_ignored():
    assert match_score("Dom Studenta nr 2", "DS 2 UW") == 1  # "dom studenta 2 ..." starts the written-out name
    assert match_score("studenta 2", "DS 2 UW") == 2
    assert match_score("ds 2", "DS 2 UW") == 1
    assert match_score("DS2", "DS 2 UW") == 1
    assert match_score("ds 2", "DS 21") is None
    assert match_score("ul. Marszałkowska", "Marszałkowska") == 0


def test_aliases_count_like_the_name():
    assert match_score("PKiN", "Pałac Kultury i Nauki", ["PKiN"]) == 0
    assert match_score("galeria mokotow", "Westfield Mokotów", ["Galeria Mokotów"]) == 0


def test_addresses_are_recognised():
    assert looks_like_address("Marszałkowska 1")
    assert looks_like_address("nowy świat 15")
    assert looks_like_address("Grójecka 17/19")
    assert looks_like_address("al. Jana Pawła II 82a")
    assert not looks_like_address("Dom Studenta nr 2")
    assert not looks_like_address("ds 2")
    assert not looks_like_address("DS2")
    assert not looks_like_address("Al. 3 Maja")
    assert not looks_like_address("politechnika")


def place(name, lat=52.2, lon=21.0, **extra):
    return {"name": name, "lat": lat, "lon": lon, **extra}


def test_better_matches_come_first():
    places = [place("Stacja Centrum"), place("Centrum Nauki"), place("Centrum")]
    assert [p["name"] for p in search("centrum", places)] == ["Centrum", "Centrum Nauki", "Stacja Centrum"]


def test_well_known_places_come_before_stops_of_the_same_quality():
    places = [place("Arkadia"), place("Westfield Arkadia", aliases=["Arkadia"], rank=0)]
    assert [p["name"] for p in search("arkadia", places)] == ["Westfield Arkadia", "Arkadia"]


def test_equal_matches_are_ordered_by_distance_to_the_user():
    far, near = place("Wilanowska", 52.17, 21.03), place("Wilanowska", 52.23, 21.0)
    assert search("wilan", [far, near], near=(52.231, 21.0))[0] is near


def test_limit_and_no_match():
    places = [place(f"Przystanek {i}") for i in range(10)]
    assert len(search("przystanek", places, limit=4)) == 4
    assert search("nic", places) == []


def test_posts_of_one_stop_become_one_place_at_their_centre():
    rows = [place("Centrum", 52.0, 21.0), place("centrum", 52.2, 21.2), place("Ratusz", 52.1, 21.1)]
    grouped = {g["name"]: g for g in group_by_name(rows)}
    assert len(grouped) == 2
    assert abs(grouped["Centrum"]["lat"] - 52.1) < 1e-9 and abs(grouped["Centrum"]["lon"] - 21.1) < 1e-9


# The user's test list: the first hit for each query, on the committed list of well-known places plus a few
# real stop names (the full stop list needs GTFS data, which tests do not load).
STOPS = ["Pl. Zbawiciela", "Plac Zbawiciela", "Metro Centrum", "Centrum", "Centrum Nauki Kopernik",
         "Metro Centrum Nauki Kopernik", "Oboźna - Kopernika", "Politechnika", "Metro Politechnika", "Dw. Centralny",
         "Dworzec Centralny", "Uwieliny - Szkoła", "Wołomin PWiK", "Lotnisko Chopina - Odloty", "Marszałkowska",
         "Nowy Świat", "DS Riviera"]


@pytest.fixture(scope="module")
def index():
    rows = json.loads(LANDMARKS.read_text(encoding="utf-8"))
    landmarks = [place(r["name"], r["lat"], r["lon"], aliases=r["aliases"], rank=0) for r in rows]
    return [prepare(p) for p in landmarks + [place(n) for n in STOPS]]


@pytest.mark.parametrize("query, first", [
    ("ds 2 uw", "DS 2 UW"),
    ("Dom Studenta nr 2", "DS 2 UW"),
    ("dom studenta nr 2", "DS 2 UW"),
    ("DS2", "DS 2 UW"),
    ("pl. zbawiciela", "Pl. Zbawiciela"),
    ("plac Zbawiciela", "Plac Zbawiciela"),
    ("zbawiciela", "Pl. Zbawiciela"),
    ("metro centrum", "Metro Centrum"),
    ("centrum nauki kopernik", "Centrum Nauki Kopernik"),
    ("kopernik", "Centrum Nauki Kopernik"),
    ("PKiN", "Pałac Kultury i Nauki"),
    ("pałac kultury", "Pałac Kultury i Nauki"),
    ("palac kultury", "Pałac Kultury i Nauki"),
    ("uw", "Uniwersytet Warszawski"),
    ("politechnika", "Politechnika"),
    ("PW", "Politechnika Warszawska"),
    ("dw. centralny", "Warszawa Centralna"),
    ("dworzec centralny", "Warszawa Centralna"),
    ("Warszawa Centralna", "Warszawa Centralna"),
    ("galeria mokotów", "Westfield Mokotów"),
    ("galeria mokotow", "Westfield Mokotów"),
    ("arkadia", "Westfield Arkadia"),
    ("lotnisko", "Lotnisko Chopina"),
    ("chopin", "Lotnisko Chopina"),
    ("łazienki", "Łazienki Królewskie"),
    ("lazienki", "Łazienki Królewskie"),
])
def test_user_list_first_hit(index, query, first):
    assert search(query, index, limit=5)[0]["name"] == first


@pytest.mark.parametrize("query, expected", [
    ("pl. zbawiciela", {"Pl. Zbawiciela", "Plac Zbawiciela"}),
    ("dw. centralny", {"Dw. Centralny", "Dworzec Centralny", "Warszawa Centralna"}),
    ("politechnika", {"Politechnika", "Politechnika Warszawska", "Metro Politechnika"}),
])
def test_user_list_all_forms_are_found(index, query, expected):
    assert expected <= {p["name"] for p in search(query, index, limit=5)}


@pytest.mark.parametrize("query", ["Marszałkowska 1", "marszalkowska 1", "nowy świat 15", "nowy swiat 15"])
def test_street_addresses_are_left_to_nominatim(index, query):
    assert looks_like_address(query)
    assert search(query, index) == []  # the stop "Marszałkowska" does not drown the address
