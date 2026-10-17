import math

import numpy as np

from station_siting import (
    cost, greedy, hex_center, hex_grid, hex_of, idw_fill, mean_per_hex, normalize, penalty, points_in_rings,
    weighted_mean_per_hex,
)

SIZE = 175.0


def test_hex_of_centre_round_trip():
    q, r, x, y = hex_grid(-3000, -3000, 3000, 3000, SIZE)
    qq, rr = hex_of(x, y, SIZE)
    assert (qq == q).all() and (rr == r).all()


def test_neighbour_spacing_and_no_gaps():
    q, r, x, y = hex_grid(-2000, -2000, 2000, 2000, SIZE)
    pts = np.c_[x, y]
    d = np.sort(np.hypot(*(pts[:, None, :] - pts[None, :, :]).transpose(2, 0, 1)), axis=1)[:, 1]
    assert np.allclose(d, SIZE * math.sqrt(3))
    # every random point is inside its hex: no farther than the circumradius from the centre
    rng = np.random.default_rng(1)
    px, py = rng.uniform(-1500, 1500, 5000), rng.uniform(-1500, 1500, 5000)
    cx, cy = hex_center(*hex_of(px, py, SIZE), SIZE)
    assert (np.hypot(px - cx, py - cy) <= SIZE + 1e-6).all()


def test_points_in_rings_with_hole():
    outer = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    hole = np.array([[4, 4], [6, 4], [6, 6], [4, 6]], dtype=float)
    inside = points_in_rings([1, 5, 11, 9], [1, 5, 5, 9], [outer, hole])
    assert inside.tolist() == [True, False, False, True]


def test_penalty():
    assert penalty(0, 1000) == 1.0
    assert penalty(1000, 1000) == 0.0
    assert penalty(np.inf, 1000) == 0.0
    assert penalty(500, 1000) == 0.25
    d = np.linspace(0, 1200, 50)
    assert (np.diff(penalty(d, 1000)) <= 0).all()


def test_cost_signs():
    base = cost(0.5, 0.5, 0.5, 2000, 1, 1, 0.5, 0.5, 1000)
    assert cost(0.9, 0.5, 0.5, 2000, 1, 1, 0.5, 0.5, 1000) < base  # more traffic -> better
    assert cost(0.5, 0.9, 0.5, 2000, 1, 1, 0.5, 0.5, 1000) < base  # more scooters -> better
    assert cost(0.5, 0.5, 0.9, 2000, 1, 1, 0.5, 0.5, 1000) > base  # less safe -> worse
    assert cost(0.5, 0.5, 0.5, 100, 1, 1, 0.5, 0.5, 1000) > base   # near a station -> worse


def test_means_and_idw():
    mean, count = mean_per_hex([0, 0, 2, -1], [1, 3, 5, 100], 4)
    assert count.tolist() == [2, 0, 1, 0]
    assert mean[0] == 2 and mean[2] == 5 and np.isnan(mean[1])
    w = weighted_mean_per_hex([0, 0], [0, 1], [3, 1], 2)
    assert w[0] == 0.25 and np.isnan(w[1])
    filled = idw_fill([0, 1, 2], [0, 0, 0], [1.0, np.nan, 3.0])
    assert filled[1] == 2.0
    assert normalize([0, 5, 10], pct=100).tolist() == [0, 0.5, 1]


def test_greedy_skips_stations_and_spreads():
    # 1-D line of 21 hexes 100 m apart, flat demand, a station at index 0
    x = np.arange(21) * 100.0
    flat = np.full(21, 0.5)
    d0 = np.abs(x - x[0])
    candidate = d0 > 0
    steps = greedy(flat, flat, np.zeros(21), d0, candidate, 2, lambda i: np.abs(x - x[i]),
                   {"alpha": 1, "beta": 1, "gamma": 0, "delta": 0, "r": 1000})
    picks = [s["pick"] for s in steps]
    assert 0 not in picks
    assert abs(x[picks[0]] - x[0]) >= 1000
    assert abs(x[picks[1]] - x[picks[0]]) >= 1000
    assert steps[0]["d_after"][picks[0]] == 0
