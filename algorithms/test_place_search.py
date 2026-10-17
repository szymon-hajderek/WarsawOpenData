from place_search import fold, group_by_name, match_score, search


def test_fold_removes_accents_and_case():
    assert fold("  Łódź-Kaliska  ") == "lodz kaliska"
    assert fold("Marszałkowska") == "marszalkowska"


def test_match_quality_order():
    assert match_score("Centrum", "Centrum") == 0
    assert match_score("cent", "Centrum") == 1
    assert match_score("politechn", "Metro Politechnika") == 2
    assert match_score("metro pol", "Metro Politechnika") == 1
    assert match_score("echni", "Metro Politechnika") == 3
    assert match_score("xyz", "Metro Politechnika") is None
    assert match_score("", "Centrum") is None


def test_words_may_come_in_any_order():
    assert match_score("politechnika metro", "Metro Politechnika") == 2


def place(name, lat=52.2, lon=21.0):
    return {"name": name, "lat": lat, "lon": lon}


def test_better_matches_come_first():
    places = [place("Stacja Centrum"), place("Centrum Nauki"), place("Centrum")]
    assert [p["name"] for p in search("centrum", places)] == ["Centrum", "Centrum Nauki", "Stacja Centrum"]


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
