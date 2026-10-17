"""Run from backend/: uv run pytest ../algorithms"""
import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from street_graph import StreetGraph
from street_model import FLAG_ELEVATOR, FLAG_STEPS, access_edges, access_flags, edge_wait, entry_wait, junctions

W = 27.0  # wait at a signal node
WALK, BIKE = 1.0, 4.0  # test speeds, m/s
CPP = Path(__file__).parent / "router" / "build" / "street_router"
needs_cpp = pytest.mark.skipif(not CPP.exists(), reason="C++ street_router not built")
K, EXTRA_M, MAX_SNAP_M = 6, 30.0, 1000.0


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


def street_graph(src, dst, walk, bike, wait, out_ids, in_ids, nodes, active=None, flags=None, lon=None, lat=None,
                 usable=None, entry=None):
    return StreetGraph(walk_speed=WALK, bike_speed=BIKE, access_k=K, access_extra_m=EXTRA_M, max_snap_m=MAX_SNAP_M,
                       src=src, dst=dst, walk=walk, bike=bike, wait=wait,
                       flags=np.zeros(len(src)) if flags is None else flags,
                       lon=np.zeros(nodes) if lon is None else lon, lat=np.zeros(nodes) if lat is None else lat,
                       usable=np.zeros(nodes, bool) if usable is None else usable,
                       entry_wait=np.zeros(nodes) if entry is None else entry,
                       out_node=out_ids, in_node=in_ids,
                       active=np.ones(len(out_ids), bool) if active is None else active)


def to_xy(lat, lon):
    """config.to_xy (the router uses the same projection)."""
    r = 6371000.0
    return np.radians(lon) * r * np.cos(np.radians(52.23)), np.radians(lat) * r


def snap(lat, lon, node_lat, node_lon, usable):
    """osm.access(): up to K nearest usable nodes, at most EXTRA_M farther than the nearest -> (nodes, dists)."""
    idx = np.nonzero(usable)[0]
    x, y = to_xy(node_lat[idx], node_lon[idx])
    d, i = cKDTree(np.c_[x, y]).query(np.c_[to_xy(lat, lon)].reshape(1, 2), k=min(K, len(idx)))
    d, i = np.atleast_1d(d.ravel()), np.atleast_1d(i.ravel())
    keep = d <= d[0] + EXTRA_M
    return idx[i[keep]], d[keep]


def grid_city():
    """A 5 x 5 street grid around 52.23 N, 21.0 E (~70 m blocks) with signal waits and one elevator edge."""
    lat = np.repeat(52.23 + np.arange(5) * 0.0006, 5)
    lon = np.tile(21.0 + np.arange(5) * 0.001, 5)
    edges = [(5 * r + c, 5 * r + c + 1) for r in range(5) for c in range(4)]
    edges += [(5 * r + c, 5 * r + c + 5) for r in range(4) for c in range(5)]
    u, v = (np.array(x) for x in zip(*edges))
    src, dst = np.r_[u, v], np.r_[v, u]
    x, y = to_xy(lat, lon)
    ln = np.hypot(x[src] - x[dst], y[src] - y[dst])
    signal = np.zeros(25, bool)
    signal[[7, 12, 17]] = True
    nw = np.where(signal, W, 0.0)
    jid = junctions(src, dst, ln, signal)
    wait = edge_wait(src, dst, nw, jid).astype(float)
    lift = ((src == 3) & (dst == 8)) | ((src == 8) & (dst == 3))
    stairs = ((src == 21) & (dst == 22)) | ((src == 22) & (dst == 21))
    wait = np.where(lift, 60.0, wait)
    flags = np.where(lift, FLAG_ELEVATOR, 0) | np.where(stairs, FLAG_STEPS, 0)
    return lat, lon, src, dst, ln, wait, flags, entry_wait(nw, jid)


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
    subprocess.run([str(CPP), "matrix", str(tmp_path / "g.bin"), str(tmp_path / "out.bin"), "--threads", "2"],
                   check=True)
    got = np.fromfile(tmp_path / "out.bin", dtype="<f4").reshape(3, 5, 5)
    want = shortest(S, D, Wm, Bm, Wt, m, out_ids, in_ids)
    for k in range(3):
        np.fill_diagonal(want[k], 0)
        want[k][~active, :] = want[k][:, ~active] = np.nan
    assert np.allclose(got, want, equal_nan=True, atol=1e-3)
    assert (got[1][np.isfinite(got[1])] > 0).any()  # some pairs ride
    assert np.isnan(got[0, 0, 3]) and np.isnan(got[0, 3, 0])  # isolated point


def coordinate_oracle(a, b, speeds=(WALK, BIKE)):
    """The expected route between two coordinates on grid_city(), built with the Python rules (snap + access)."""
    lat, lon, src, dst, ln, wait, _, entry = grid_city()
    n = len(lat)
    (na, da), (nb, db) = snap(*a, lat, lon, np.ones(n, bool)), snap(*b, lat, lon, np.ones(n, bool))
    # point A = node n (seeds: walk d, entry wait), point B = node n + 1 (walk d, no wait)
    S = np.r_[src, np.full(len(na), n), nb]
    D = np.r_[dst, na, np.full(len(nb), n + 1)]
    Wm, Wt = np.r_[ln, da, db], np.r_[wait, entry[na], np.zeros(len(nb))]
    global WALK, BIKE
    old = WALK, BIKE
    WALK, BIKE = speeds
    try:
        walk, _, w = shortest(S, D, Wm, np.zeros(len(S)), Wt, n + 2, [n], [n + 1])
    finally:
        WALK, BIKE = old
    return walk[0, 0], w[0, 0], walk[0, 0] / speeds[0] + w[0, 0], da[0], db[0]


def save_grid(path):
    lat, lon, src, dst, ln, wait, flags, entry = grid_city()
    street_graph(src, dst, ln, np.zeros(len(src)), wait, np.zeros(0, int), np.zeros(0, int), len(lat),
                 flags=flags, lon=lon, lat=lat, usable=np.ones(len(lat), bool), entry=entry).save(path)


METRO_ACCESS_M, ELEVATOR_S, TRANSFER_M = 150.0, 60.0, 200.0


def save_overlay(path):
    """A toy stations.json next to the street graphs: a bus post at node 24, a metro station with two platforms
    (P1, P2) reached through two entrances near nodes 0 and 4, with an in-station transfer."""
    lat, lon, *_ = grid_city()
    loc = lambda id_, kind, la, lo, **extra: {"id": id_, "kind": kind, "position": {"lat": la, "lon": lo},
                                              "entrances": [], "transfers": [], **extra}
    doc = {"hash": "toy", "constants": {"metro_access_m": METRO_ACCESS_M, "elevator_s": ELEVATOR_S,
                                        "no_steps": ["bike", "accessible"]},
           "locations": [
               loc("ztm:post24", "bus_post", lat[24], lon[24]),
               loc("ztm:M:P1", "metro_platform", lat[2], lon[2],
                   entrances=[{"lat": lat[0] + 0.00001, "lon": lon[0]}, {"lat": lat[4] + 0.00001, "lon": lon[4]}],
                   transfers=[{"to": "ztm:M:P2", "walk_m": TRANSFER_M}]),
               loc("ztm:M:P2", "metro_platform", lat[2], lon[2],  # its only entrance is in the far corner
                   entrances=[{"lat": lat[24] + 0.00001, "lon": lon[24]}],
                   transfers=[{"to": "ztm:M:P1", "walk_m": TRANSFER_M}])]}
    path.write_text(json.dumps(doc))


A, B = (52.2301, 21.0003), (52.2323, 21.0039)  # two coordinates inside the grid, between nodes


@needs_cpp
def test_cpp_route_between_coordinates_matches_the_python_rules(tmp_path):
    save_grid(tmp_path / "graph_walk.bin")
    out = subprocess.run([str(CPP), "route", str(tmp_path / "graph_walk.bin"), f"{A[0]},{A[1]}", f"{B[0]},{B[1]}"],
                         check=True, capture_output=True, text=True).stdout
    got = json.loads(out)
    walk, wait, seconds, snap_a, snap_b = coordinate_oracle(A, B)
    assert np.isclose(got["walk_m"], walk, atol=0.11) and np.isclose(got["wait_s"], wait, atol=0.11)
    assert np.isclose(got["seconds"], seconds, atol=0.11) and got["bike_m"] == 0
    assert np.allclose(got["snap_m"], [snap_a, snap_b], atol=0.11)
    assert got["path"][0] == [A[1], A[0]] and got["path"][-1] == [B[1], B[0]]


@needs_cpp
def test_cpp_route_far_point_is_refused(tmp_path):
    save_grid(tmp_path / "graph_walk.bin")
    r = subprocess.run([str(CPP), "route", str(tmp_path / "graph_walk.bin"), "52.30,21.0", f"{B[0]},{B[1]}"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "from the street graph" in json.loads(r.stdout)["error"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(port, body, path="/route"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@needs_cpp
def start_server(tmp_path, mode="walk"):
    street = tmp_path / "street"
    street.mkdir(exist_ok=True)
    save_grid(street / f"graph_{mode}.bin")
    save_overlay(tmp_path / "stations.json")
    port = free_port()
    proc = subprocess.Popen([str(CPP), "serve", str(street), "--port", str(port), "--threads", "2"],
                            stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as r:
                health = json.loads(r.read())
            break
        except urllib.error.URLError:
            time.sleep(0.05)
    else:
        proc.kill()
        raise RuntimeError("server did not start")
    return proc, port, health


def test_cpp_server(tmp_path):
    proc, port, health = start_server(tmp_path)
    try:
        assert health["modes"]["walk"]["nodes"] == 25 and health["stations"]["count"] == 3
        assert health["matrices"]["status"] == "missing"
        ok = {"from": list(A), "to": list(B), "mode": "walk"}
        status, got = post(port, ok)
        assert status == 200 and np.isclose(got["seconds"], coordinate_oracle(A, B)[2], atol=0.11)
        # the elevator on 3 <-> 8 and the steps on 21 <-> 22 are reported where the path enters them
        status, got = post(port, {**ok, "from": [52.2300, 21.0030], "to": [52.2306, 21.0030]})
        assert status == 200 and got["elevators"] == [[21.003, 52.23]]
        status, got = post(port, {**ok, "from": [52.2324, 21.0010], "to": [52.2324, 21.0020]})
        assert status == 200 and got["steps"] == [[21.001, 52.2324]]
        # speeds from the query: a fast walker can pick another path than a slow one; both match the oracle
        for speeds in ((0.5, BIKE), (6.0, BIKE)):
            status, got = post(port, {**ok, "speeds": {"walk": speeds[0], "bike": speeds[1]}})
            assert status == 200 and np.isclose(got["seconds"], coordinate_oracle(A, B, speeds)[2], atol=0.11)
        assert post(port, {**ok, "preferences": {"maxTransfers": 1}}) == \
            (501, {"error": "not implemented", "unimplemented": ["preferences"]})
        assert post(port, {**ok, "speeds": {"walk": 1.0, "scooter": 5}})[0] == 501
        assert post(port, {**ok, "mode": "car"})[0] == 400
        assert post(port, {**ok, "speeds": {"walk": 0}})[0] == 400
        assert post(port, {**ok, "to": [52.30, 21.0]})[0] == 422
    finally:
        proc.terminate()
        proc.wait()


@needs_cpp
def test_cpp_server_resolves_station_ids_and_metro_entrances(tmp_path):
    proc, port, _ = start_server(tmp_path)
    lat, lon, *_ = grid_city()
    try:
        # a bus post by id = the same route as its coordinates
        by_id = post(port, {"from": list(A), "to": "ztm:post24", "mode": "walk"})
        by_xy = post(port, {"from": list(A), "to": [lat[24], lon[24]], "mode": "walk"})
        assert by_id[0] == by_xy[0] == 200 and by_id[1]["seconds"] == by_xy[1]["seconds"]
        assert by_id[1]["to_id"] == "ztm:post24"
        # a metro platform is reached through its nearest entrance: + 150 m walked, no elevator in walk mode
        status, got = post(port, {"from": [lat[1], lon[1]], "to": "ztm:M:P1", "mode": "walk"})
        walk_to_entrance, _, _, _, _ = coordinate_oracle((lat[1], lon[1]), (lat[0] + 0.00001, lon[0]))
        assert status == 200 and np.isclose(got["walk_m"], walk_to_entrance + METRO_ACCESS_M, atol=0.2)
        assert got["wait_s"] == 0
        assert post(port, {"from": list(A), "to": "ztm:nope", "mode": "walk"})[0] == 404
    finally:
        proc.terminate()
        proc.wait()


@needs_cpp
def test_cpp_route_from_several_starts_each_with_its_own_start_time(tmp_path):
    # the egress after RAPTOR: every station has its own arrival time; the cheapest start + walk wins
    proc, port, _ = start_server(tmp_path)
    lat, lon, *_ = grid_city()
    try:
        end = [lat[20], lon[20]]
        post_s = post(port, {"from": "ztm:post24", "to": end, "mode": "walk"})[1]["seconds"]
        metro_s = post(port, {"from": "ztm:M:P1", "to": end, "mode": "walk"})[1]["seconds"]
        for at_post, at_metro in ((0, 1000), (1000, 0)):
            status, got = post(port, {"from": [{"id": "ztm:post24", "at_s": at_post}, {"id": "ztm:M:P1", "at_s": at_metro}],
                                      "to": end, "mode": "walk"})
            assert status == 200
            best = min((at_post + post_s, 0, "ztm:post24"), (at_metro + metro_s, 1, "ztm:M:P1"))
            assert np.isclose(got["seconds"], best[0], atol=0.2)
            assert got["from_index"] == best[1] and got["from_id"] == best[2]
            assert got["start_s"] == (at_post, at_metro)[best[1]]
        # a coordinate start works too; a list as "to" does not
        status, got = post(port, {"from": [{"point": end, "at_s": 5}], "to": end, "mode": "walk"})
        assert status == 200 and np.isclose(got["seconds"], 5, atol=0.2)
        assert post(port, {"from": list(A), "to": [{"id": "ztm:post24"}], "mode": "walk"})[0] == 400
        assert post(port, {"from": [{"at_s": 1}], "to": end, "mode": "walk"})[0] == 400
    finally:
        proc.terminate()
        proc.wait()


@needs_cpp
def test_cpp_access_lists_stations_within_the_limit_both_ways(tmp_path):
    proc, port, _ = start_server(tmp_path)
    lat, lon, *_ = grid_city()
    try:
        status, got = post(port, {"point": [lat[1], lon[1]], "mode": "walk", "direction": "from", "limit_s": 3000}
                           | {}, path="/access")
        assert status == 200
        by = {s["id"]: s for s in got["stations"]}
        # P1 through the near entrance; P2 (entrance in the far corner) through the in-station transfer (200 m more)
        walk_to_entrance = coordinate_oracle((lat[1], lon[1]), (lat[0] + 0.00001, lon[0]))[0]
        assert np.isclose(by["ztm:M:P1"]["walk_m"], walk_to_entrance + METRO_ACCESS_M, atol=0.2)
        assert np.isclose(by["ztm:M:P2"]["walk_m"], by["ztm:M:P1"]["walk_m"] + TRANSFER_M, atol=0.2)
        # the post: the same as a plain route to its coordinates
        route_s = post(port, {"from": [lat[1], lon[1]], "to": [lat[24], lon[24]], "mode": "walk"})[1]["seconds"]
        assert np.isclose(by["ztm:post24"]["seconds"], route_s, atol=0.2)
        # a tight limit drops the far post
        status, got = post(port, {"point": [lat[1], lon[1]], "mode": "walk", "direction": "from", "limit_s": 200},
                           path="/access")
        assert status == 200 and "ztm:post24" not in {s["id"] for s in got["stations"]}
        # direction "to": the time from the post to the point equals the plain route in that direction
        status, got = post(port, {"point": [lat[1], lon[1]], "mode": "walk", "direction": "to", "limit_s": 3000},
                           path="/access")
        back = post(port, {"from": [lat[24], lon[24]], "to": [lat[1], lon[1]], "mode": "walk"})[1]["seconds"]
        assert status == 200 and np.isclose({s["id"]: s for s in got["stations"]}["ztm:post24"]["seconds"], back, atol=0.2)
        assert post(port, {"point": [lat[1], lon[1]], "mode": "walk", "veturilo": True}, path="/access")[0] == 501
    finally:
        proc.terminate()
        proc.wait()
