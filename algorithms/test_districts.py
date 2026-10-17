from districts import blocked, in_district


def test_srodmiescie_contains_the_palace_of_culture():
    assert in_district(52.2318, 21.0060, "Śródmieście")
    assert not in_district(52.2318, 21.0060, "Ursynów")


def test_a_point_blocks_its_circle_only():
    assert blocked(52.23, 21.01, [], [(52.23, 21.01, 200)], lambda a, b: 0)
    assert not blocked(52.23, 21.01, [], [(52.30, 21.10, 100)], lambda a, b: 5000)


def test_an_unknown_district_name_blocks_nothing():
    assert not in_district(52.23, 21.01, "Nieistniejąca")
