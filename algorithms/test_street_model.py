"""Run from backend/: uv run pytest ../algorithms"""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from street_graph import StreetGraph
from street_model import FLAG_ELEVATOR, access_edges, access_flags, edge_wait, entry_wait, junctions

W = 27.0  # wait at a signal node
WALK, BIKE = 1.0, 4.0  # test speeds, m/s
CPP = Path(__file__).parent / "router" / "preprocess" / "build" / "street_matrix"
needs_cpp = pytest.mark.skipif(not CPP.exists(), reason="C++ street_matrix not built")


def both_ways(edges):
    """[(u, v, length)] -> directed arrays with both directions."""
    u, v, ln = (np.array(x) for x in zip(*edges))
    return np.r_[u, v], np.r_[v, u], np.r_[ln, ln].astype(float)


def shortest(src, dst, walk, bike, wait, n, sources, targets):
    """Test oracle: scipy Dijkstra on walk / WALK + bike / BIKE + wait, then walk, bike and wait summed along
    each path. Returns three (sources x targets) matrices; no path = NaN."""
    best = {}  # (u, v) -> (cost, walk, bike, wait) of the cheapest parallel edge
    for u, v, wm, bm, w in zip(src.tolist(), dst.tolist(), walk, bike, wait):
        c = wm / WALK + bm / BIKE + w
        if (u, v) not in best or c < best[(u, v)][0]:
            best[(u, v)] = (c, wm, bm, w)
    uv = np.array(list(best))
    g = csr_matrix(([e[0] + 1e-3 for e in best.values()], (uv[:, 0], uv[:, 1])), shape=(n, n))
    out = np.full((3, len(sources), len(targets)), np.nan)
    for r, s in enumerate(sources):
        cost, pred = dijkstra(g, indices=s, return_predecessors=True)
        for k, t in enumerate(targets):
            if not np.isfinite(cost[t]):
                continue
            total, v = np.zeros(3), t
            while v != s:
                total += best[(int(pred[v]), int(v))][1:]
                v = int(pred[v])
            out[:, r, k] = total
    return out


def with_signals(src, dst, length, n, signals, sources, targets):
    """Walked street with signal waits -> (walk, wait, junction ids)."""
    signal = np.zeros(n, dtype=bool)
    signal[list(signals)] = True
    jid = junctions(src, dst, length, signal)
    w = edge_wait(src, dst, np.where(signal, W, 0.0), jid).astype(float)
    walk, _, wait = shortest(src, dst, length, np.zeros(len(src)), w, n, sources, targets)
    return walk, wait, jid


def with_points(src, dst, walk, bike, wait, n, nodes, dist, **access):
    """Street edges + access_edges -> (src, dst, walk, bike, wait, out_ids, in_ids, nodes incl. virtual)."""
    vs, vd, vwalk, vwait, out_ids, in_ids = access_edges(n, np.asarray(nodes), np.asarray(dist, dtype=float),
                                                         **access)
    return (np.r_[src, vs], np.r_[dst, vd], np.r_[walk, vwalk], np.r_[bike, np.zeros(len(vs))], np.r_[wait, vwait],
            out_ids, in_ids, n + 2 * len(out_ids))


def street_graph(src, dst, walk, bike, wait, out_ids, in_ids, nodes, active=None, flags=None, lon=None, lat=None):
    return StreetGraph(src=src, dst=dst, cost=walk / WALK + bike / BIKE + wait, walk=walk, bike=bike, wait=wait,
                       flags=np.zeros(len(src)) if flags is None else flags,
                       lon=np.zeros(nodes) if lon is None else lon, lat=np.zeros(nodes) if lat is None else lat,
                       out_node=out_ids, in_node=in_ids,
                       active=np.ones(len(out_ids), bool) if active is None else active)


# ---------------------------------------------------------------- cost model


def test_distance_along_a_line():
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 20), (2, 3, 30)])
    dist, wait, _ = with_signals(src, dst, ln, 4, [], [0], [0, 3])
    assert np.allclose(dist, [[0, 60]]) and np.allclose(wait, [[0, 0]])


def test_close_signals_pay_once():
    # 0 -- 1(signal) -10 m- 2(signal) -- 3
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 10), (2, 3, 50)])
    _, wait, jid = with_signals(src, dst, ln, 4, [1, 2], [0, 3], [3, 0])
    assert jid[1] == jid[2] >= 0
    assert np.allclose(wait, [[W, 0], [0, W]])


def test_far_signals_pay_twice():
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 100), (2, 3, 50)])
    _, wait, jid = with_signals(src, dst, ln, 4, [1, 2], [0], [3])
    assert jid[1] != jid[2]
    assert np.allclose(wait, [[2 * W]])


def test_island_between_signals_is_part_of_junction():
    # 0 -- 1(signal) -5- 2(island) -5- 3(signal) -- 4
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 5), (2, 3, 5), (3, 4, 50)])
    _, wait, jid = with_signals(src, dst, ln, 5, [1, 3], [0], [4])
    assert jid[1] == jid[2] == jid[3] >= 0
    assert np.allclose(wait, [[W]])


def test_entering_through_island_still_pays():
    # 5 is a side path that reaches the island 2 directly, then crosses signal 3
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 5), (2, 3, 5), (3, 4, 50), (5, 2, 20)])
    _, wait, jid = with_signals(src, dst, ln, 6, [1, 3], [5, 4], [4, 5])
    assert jid[2] >= 0
    assert np.allclose(wait, [[W, 0], [0, W]])


def test_sidewalk_near_signal_still_pays():
    # 5 is a sidewalk node 5 m from signal 1, not between two signals
    src, dst, ln = both_ways([(0, 1, 50), (1, 2, 10), (2, 3, 50), (5, 1, 5), (4, 5, 50)])
    _, wait, jid = with_signals(src, dst, ln, 6, [1, 2], [4], [3])
    assert jid[5] == -1
    assert np.allclose(wait, [[W]])


def test_walk_both_directions_pay_the_same():
    # a grid with signals; for end points outside junctions A -> B and B -> A cost the same
    edges = [(5 * r + c, 5 * r + c + 1, 10 + 5 * r + c) for r in range(5) for c in range(4)]
    edges += [(5 * r + c, 5 * r + c + 5, 12 + 5 * r + c) for r in range(4) for c in range(5)]
    src, dst, ln = both_ways(edges)
    nodes = [i for i in range(25) if i not in (6, 7, 11, 12, 13, 17, 18)]  # no signal / island nodes
    dist, wait, _ = with_signals(src, dst, ln, 25, [6, 7, 12, 17, 18], nodes, nodes)
    cost = dist / WALK + wait
    assert np.allclose(cost, cost.T)


def test_oneway_is_asymmetric_and_unreachable_is_nan():
    # 0 -> 1 directly (oneway), back only through 2 (long); node 3 is isolated
    src, dst, ln = np.array([0, 1, 2]), np.array([1, 2, 0]), np.array([10.0, 50.0, 50.0])
    dist, _, _ = with_signals(src, dst, ln, 4, [], [0, 1], [1, 0, 3])
    assert np.allclose(dist[:, :2], [[10, 0], [0, 100]])
    assert np.isnan(dist[:, 2]).all()


# ---------------------------------------------------------------- joining points to the graph


def test_access_edges_pick_the_best_node_and_never_pass_through_a_point():
    # street 0 - 1 - 2 (oneway 0 -> 1 -> 2). Point A sits between 1 and 2, point B near 0.
    S, D, Wm, Bm, Wt, out_ids, in_ids, m = with_points(
        np.array([0, 1]), np.array([1, 2]), np.array([100.0, 100.0]), np.zeros(2), np.zeros(2), 3,
        [[1, 2], [0, 0]], [[60.0, 40.0], [5.0, np.inf]])
    walk, _, _ = shortest(S, D, Wm, Bm, Wt, m, out_ids, in_ids)
    # B -> A: 5 to node 0, 100 to node 1, 60 to A (cheaper than going on to node 2 and back 40)
    assert np.isclose(walk[1, 0], 165)
    # A -> B: the street is oneway away from 0, and A's in / out nodes are separate: no path
    assert np.isnan(walk[0, 1])


def test_metro_platform_walks_down_from_the_best_of_all_entrances():
    # street 0 - 1 - 2 - 3 (10 m each). Point 0 is a bus stop at node 0.
    # Point 1 is a metro platform with two entrances: near node 3 (far) and near node 1 (near);
    # each is a 150 m walk down plus a 60 s elevator.
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 10), (2, 3, 10)])
    z = np.zeros(len(src))
    S, D, Wm, Bm, Wt, out_ids, in_ids, m = with_points(src, dst, ln, z, z, 4, [[0], [3], [1]], [[0.0], [2.0], [4.0]],
                                                       owner=[0, 1, 1], fixed_m=[0, 150, 150], fixed_s=[0, 60, 60],
                                                       n_points=2)
    walk, bike, wait = shortest(S, D, Wm, Bm, Wt, m, out_ids, in_ids)
    assert np.allclose([walk[0, 1], wait[0, 1], bike[0, 1]], [164, 60, 0])  # via the near entrance
    assert np.allclose([walk[1, 0], wait[1, 0]], [164, 60])


def test_point_at_a_signal_pays_the_same_both_ways():
    # 0 -- 1(signal) -- 2. Point A joins at the signal node 1, point B at node 2.
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 20)])
    nw = np.array([0.0, W, 0.0])
    jid = junctions(src, dst, ln, nw > 0)
    S, D, Wm, Bm, Wt, out_ids, in_ids, m = with_points(src, dst, ln, np.zeros(len(src)),
                                                       edge_wait(src, dst, nw, jid).astype(float), 3,
                                                       [[1], [2]], [[3.0], [3.0]], node_entry=entry_wait(nw, jid))
    _, _, wait = shortest(S, D, Wm, Bm, Wt, m, out_ids, in_ids)
    assert np.isclose(wait[0, 1], W) and np.isclose(wait[1, 0], W)


# ---------------------------------------------------------------- the C++ program


@needs_cpp
def test_cpp_matrix_matches_the_oracle(tmp_path):
    # grid with signals, ridden and walked edges, a oneway edge, an isolated point and an inactive point
    rng = np.random.default_rng(5)
    edges = [(5 * r + c, 5 * r + c + 1, rng.uniform(5, 50)) for r in range(5) for c in range(4)]
    edges += [(5 * r + c, 5 * r + c + 5, rng.uniform(5, 50)) for r in range(4) for c in range(5)]
    src, dst, ln = both_ways(edges)
    src, dst, ln = np.r_[src, 3], np.r_[dst, 21], np.r_[ln, 7.0]  # a oneway shortcut
    n = 26  # node 25 is isolated
    signal = np.zeros(n, dtype=bool)
    signal[[6, 7, 12, 18]] = True
    w = edge_wait(src, dst, np.where(signal, W, 0.0), junctions(src, dst, ln, signal)).astype(float)
    ridden = rng.random(len(src)) < 0.5
    nodes = [[0, 1], [12, 13], [24, 19], [25, 25], [8, 9]]
    dist = [[3.0, 9.0], [4.0, np.inf], [2.0, 20.0], [1.0, np.inf], [5.0, 6.0]]
    S, D, Wm, Bm, Wt, out_ids, in_ids, m = with_points(src, dst, np.where(ridden, 0, ln), np.where(ridden, ln, 0), w,
                                                       n, nodes, dist)
    active = np.array([1, 1, 1, 1, 0], dtype=bool)
    street_graph(S, D, Wm, Bm, Wt, out_ids, in_ids, m, active).save(tmp_path / "g.bin")
    subprocess.run([str(CPP), str(tmp_path / "g.bin"), str(tmp_path / "out.bin"), "--threads", "2"], check=True)
    got = np.fromfile(tmp_path / "out.bin", dtype="<f4").reshape(3, 5, 5)
    want = shortest(S, D, Wm, Bm, Wt, m, out_ids, in_ids)
    for k in range(3):
        np.fill_diagonal(want[k], 0)
        want[k][~active, :] = want[k][:, ~active] = np.nan
    assert np.allclose(got, want, equal_nan=True, atol=1e-3)
    assert (got[1][np.isfinite(got[1])] > 0).any()  # some pairs ride
    assert np.isnan(got[0, 0, 3]) and np.isnan(got[0, 3, 0])  # isolated point


@needs_cpp
def test_cpp_route_gives_the_path_and_the_elevator(tmp_path):
    # street 0 - 1 - 2 - 3 along a line of longitudes; the edge 1 <-> 2 is an elevator
    src, dst, ln = both_ways([(0, 1, 10), (1, 2, 5), (2, 3, 10)])
    lift = ((src == 1) & (dst == 2)) | ((src == 2) & (dst == 1))
    dist = np.array([[2.0], [2.0]])
    S, D, Wm, Bm, Wt, out_ids, in_ids, m = with_points(src, dst, ln, np.zeros(len(src)), np.where(lift, 60.0, 0.0),
                                                       4, [[0], [3]], dist)
    flags = np.r_[np.where(lift, FLAG_ELEVATOR, 0), access_flags(dist, [0, 0])]
    lon = np.r_[[21.0, 21.0001, 21.0002, 21.0003], [20.9999, 21.0004], [20.9999, 21.0004]]
    street_graph(S, D, Wm, Bm, Wt, out_ids, in_ids, m, flags=flags, lon=lon, lat=np.full(m, 52.2)).save(
        tmp_path / "g.bin")
    out = subprocess.run([str(CPP), str(tmp_path / "g.bin"), "--route", "0", "1", "--route", "1", "0"],
                         check=True, capture_output=True, text=True).stdout.splitlines()
    there, back = (json.loads(x) for x in out)
    assert there["path"] == [[20.9999, 52.2], [21.0, 52.2], [21.0001, 52.2], [21.0002, 52.2], [21.0003, 52.2],
                             [21.0004, 52.2]]
    assert np.allclose([there["walk_m"], there["bike_m"], there["wait_s"]], [29, 0, 60])
    assert there["elevators"] == [[21.0001, 52.2]] and there["metro_entrances"] == []  # where it is boarded
    assert back["path"] == there["path"][::-1] and back["elevators"] == [[21.0002, 52.2]]
