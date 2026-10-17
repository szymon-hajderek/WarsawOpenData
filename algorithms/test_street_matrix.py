"""Run from backend/: uv run pytest ../algorithms"""
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from street_matrix import EPS, EdgeLookup, access_edges, edge_wait, entry_wait, junctions, matrix_rows, save_graph

W = 27.0  # wait at a signal node
SPEED = 1.0


def both_ways(edges):
    """[(u, v, length)] -> directed arrays with both directions."""
    u, v, ln = (np.array(x) for x in zip(*edges))
    return np.r_[u, v], np.r_[v, u], np.r_[ln, ln].astype(float)


def solve(src, dst, length, n, signals, sources, targets, snap_s=None, snap_t=None):
    signal = np.zeros(n, dtype=bool)
    signal[list(signals)] = True
    jid = junctions(src, dst, length, signal)
    w = edge_wait(src, dst, np.where(signal, W, 0.0), jid).astype(float)
    cost = length / SPEED + w
    g = csr_matrix((cost + EPS, (src, dst)), shape=(n, n))
    lookup = EdgeLookup(src, dst, length, w, cost, n)
    s, t = np.array(sources), np.array(targets)
    snap_s = np.zeros(len(s)) if snap_s is None else np.array(snap_s)
    snap_t = np.zeros(len(t)) if snap_t is None else np.array(snap_t)
    dist, wait = matrix_rows(g, lookup, s, t, snap_s, snap_t)
    return dist, wait, jid


def test_distance_and_snap():
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 20), (2, 3, 30)])
    dist, wait, _ = solve(src, dst, ln, 4, [], [0], [0, 3], snap_s=[5], snap_t=[0, 7])
    assert np.allclose(dist, [[5, 72]])
    assert np.allclose(wait, [[0, 0]])


def test_close_signals_pay_once():
    # 0 -- 1(signal) -10 m- 2(signal) -- 3
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 10), (2, 3, 50)])
    _, wait, jid = solve(src, dst, ln, 4, [1, 2], [0, 3], [3, 0])
    assert jid[1] == jid[2] >= 0
    assert np.allclose(wait, [[W, 0], [0, W]])


def test_far_signals_pay_twice():
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 100), (2, 3, 50)])
    _, wait, jid = solve(src, dst, ln, 4, [1, 2], [0], [3])
    assert jid[1] != jid[2]
    assert np.allclose(wait, [[2 * W]])


def test_island_between_signals_is_part_of_junction():
    # 0 -- 1(signal) -5- 2(island) -5- 3(signal) -- 4
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 5), (2, 3, 5), (3, 4, 50)])
    _, wait, jid = solve(src, dst, ln, 5, [1, 3], [0], [4])
    assert jid[1] == jid[2] == jid[3] >= 0
    assert np.allclose(wait, [[W]])


def test_entering_through_island_still_pays():
    # 5 is a side path that reaches the island 2 directly, then crosses signal 3
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 5), (2, 3, 5), (3, 4, 50), (5, 2, 20)])
    _, wait, jid = solve(src, dst, ln, 6, [1, 3], [5, 4], [4, 5])
    assert jid[2] >= 0
    assert np.allclose(wait, [[W, 0], [0, W]])


def test_walk_both_directions_pay_the_same():
    # a grid with signals; on an undirected graph A -> B and B -> A must cost the same
    # (for end points outside junctions: a wait is paid when a node is entered, never at the start)
    edges, signals = [], [6, 7, 12, 17, 18]
    for r in range(5):
        for c in range(5):
            i = 5 * r + c
            if c < 4:
                edges.append((i, i + 1, 10 + i))
            if r < 4:
                edges.append((i, i + 5, 12 + i))
    src, dst, ln = both_ways(edges)
    nodes = [i for i in range(25) if i not in (6, 7, 11, 12, 13, 17, 18)]  # no signal / island nodes
    dist, wait, _ = solve(src, dst, ln, 25, signals, nodes, nodes)
    cost = dist / SPEED + wait
    assert np.allclose(cost, cost.T)


def test_sidewalk_near_signal_still_pays():
    # 5 is a sidewalk node 5 m from signal 1, not between two signals
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 10), (2, 3, 50), (5, 1, 5), (4, 5, 50)])
    _, wait, jid = solve(src, dst, ln, 6, [1, 2], [4], [3])
    assert jid[5] == -1
    assert np.allclose(wait, [[W]])


def test_oneway_is_asymmetric_and_unreachable_is_nan():
    # 0 -> 1 directly (oneway), back only through 2 (long); node 3 is isolated
    src = np.array([0, 1, 2])
    dst = np.array([1, 2, 0])
    ln = np.array([10.0, 50.0, 50.0])
    dist, _, _ = solve(src, dst, ln, 4, [], [0, 1], [1, 0, 3])
    assert np.allclose(dist[:, :2], [[10, 0], [0, 100]])
    assert np.isnan(dist[:, 2]).all()


def test_access_edges_pick_the_best_node_and_never_pass_through_a_point():
    # street 0 - 1 - 2 (oneway 0 -> 1 -> 2). Point A sits between 1 and 2, point B near 0.
    src, dst, ln = np.array([0, 1]), np.array([1, 2]), np.array([100.0, 100.0])
    nodes = np.array([[1, 2], [0, 0]])
    dist = np.array([[60.0, 40.0], [5.0, np.inf]])
    vs, vd, vl, vw, out_ids, in_ids = access_edges(3, nodes, dist, extra_s_per_m=0.5)
    S, D, L, Wt = np.r_[src, vs], np.r_[dst, vd], np.r_[ln, vl], np.r_[np.zeros(2), vw]
    cost = L + Wt
    n = 3 + 2 * 2
    g = csr_matrix((cost + EPS, (S, D)), shape=(n, n))
    lookup = EdgeLookup(S, D, L, Wt, cost, n)
    dist_m, wait_s = matrix_rows(g, lookup, out_ids, in_ids, np.zeros(2), np.zeros(2))
    # B -> A: 5 to node 0, 100 to node 1, 60 to A (cheaper than going on to node 2 and back 40)
    assert np.isclose(dist_m[1, 0], 165) and np.isclose(wait_s[1, 0], 0.5 * 65)
    # A -> B: the street is oneway away from 0, and A's in/out nodes are separate: no path
    assert np.isnan(dist_m[0, 1])


CPP = Path(__file__).parent / "router" / "preprocess" / "build" / "street_matrix"


@pytest.mark.skipif(not CPP.exists(), reason="C++ street_matrix not built")
def test_cpp_matches_python(tmp_path):
    # grid with signals, a oneway edge, an isolated point and an inactive point
    rng = np.random.default_rng(5)
    edges = [(5 * r + c, 5 * r + c + 1, rng.uniform(5, 50)) for r in range(5) for c in range(4)]
    edges += [(5 * r + c, 5 * r + c + 5, rng.uniform(5, 50)) for r in range(4) for c in range(5)]
    src, dst, ln = both_ways(edges)
    src, dst, ln = np.r_[src, 3], np.r_[dst, 21], np.r_[ln, 7.0]  # a oneway shortcut
    n = 26  # node 25 is isolated
    signal = np.zeros(n, dtype=bool)
    signal[[6, 7, 12, 18]] = True
    jid = junctions(src, dst, ln, signal)
    w = edge_wait(src, dst, np.where(signal, W, 0.0), jid).astype(float)
    nodes = np.array([[0, 1], [12, 13], [24, 19], [25, 25], [8, 9]])
    dist = np.array([[3.0, 9.0], [4.0, np.inf], [2.0, 20.0], [1.0, np.inf], [5.0, 6.0]])
    vs, vd, vl, vw, out_ids, in_ids = access_edges(n, nodes, dist, extra_s_per_m=0.3)
    S, D, L, Wt = np.r_[src, vs], np.r_[dst, vd], np.r_[ln, vl], np.r_[w, vw]
    cost, m = L / SPEED + Wt, n + 2 * len(out_ids)
    active = np.array([1, 1, 1, 1, 0], dtype=bool)
    save_graph(tmp_path / "g.bin", m, S, D, cost, L, Wt, out_ids, in_ids, active)
    subprocess.run([str(CPP), str(tmp_path / "g.bin"), str(tmp_path / "out.bin"), "--threads", "2"], check=True)
    got = np.fromfile(tmp_path / "out.bin", dtype="<f4").reshape(2, 5, 5)
    g = csr_matrix((cost + EPS, (S, D)), shape=(m, m))
    want_d, want_w = matrix_rows(g, EdgeLookup(S, D, L, Wt, cost, m), out_ids, in_ids, np.zeros(5), np.zeros(5))
    np.fill_diagonal(want_d, 0)
    np.fill_diagonal(want_w, 0)
    want_d[~active, :] = want_d[:, ~active] = np.nan
    want_w[~active, :] = want_w[:, ~active] = np.nan
    assert np.allclose(got[0], want_d, equal_nan=True, atol=1e-3)
    assert np.allclose(got[1], want_w, equal_nan=True, atol=1e-3)
    assert np.isnan(got[0, 0, 3]) and np.isnan(got[0, 3, 0])  # isolated point


def test_metro_platform_uses_the_best_of_all_entrances():
    # street 0 - 1 - 2 - 3 (10 m each). Point 0 is a bus stop at node 0.
    # Point 1 is a metro platform with two entrances: near node 3 (far) and near node 1 (near), +120 s each.
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 10), (2, 3, 10)])
    nodes = np.array([[0], [3], [1]])  # sites: stop, entrance A, entrance B
    dist = np.array([[0.0], [2.0], [4.0]])
    vs, vd, vl, vw, out_ids, in_ids = access_edges(4, nodes, dist, owner=[0, 1, 1], fixed_s=[0, 120, 120],
                                                   n_points=2)
    S, D, L, Wt = np.r_[src, vs], np.r_[dst, vd], np.r_[ln, vl], np.r_[np.zeros(len(src)), vw]
    cost, m = L / SPEED + Wt, 4 + 4
    g = csr_matrix((cost + EPS, (S, D)), shape=(m, m))
    dist_m, wait_s = matrix_rows(g, EdgeLookup(S, D, L, Wt, cost, m), out_ids, in_ids, np.zeros(2), np.zeros(2))
    assert np.isclose(dist_m[0, 1], 14) and np.isclose(wait_s[0, 1], 120)  # via the near entrance
    assert np.isclose(dist_m[1, 0], 14) and np.isclose(wait_s[1, 0], 120)


def test_point_at_a_signal_pays_the_same_both_ways():
    # 0 -- 1(signal) -- 2. Point A joins at the signal node 1, point B at node 2.
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 20)])
    n = 3
    nw = np.array([0.0, W, 0.0])
    jid = junctions(src, dst, ln, nw > 0)
    w = edge_wait(src, dst, nw, jid).astype(float)
    vs, vd, vl, vw, out_ids, in_ids = access_edges(n, np.array([[1], [2]]), np.array([[3.0], [3.0]]),
                                                   node_entry=entry_wait(nw, jid))
    S, D, L, Wt = np.r_[src, vs], np.r_[dst, vd], np.r_[ln, vl], np.r_[w, vw]
    cost, m = L / SPEED + Wt, n + 4
    g = csr_matrix((cost + EPS, (S, D)), shape=(m, m))
    _, wait_s = matrix_rows(g, EdgeLookup(S, D, L, Wt, cost, m), out_ids, in_ids, np.zeros(2), np.zeros(2))
    assert np.isclose(wait_s[0, 1], W) and np.isclose(wait_s[1, 0], W)
