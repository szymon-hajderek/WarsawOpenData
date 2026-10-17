"""Street paths between many points: signal junctions (wait counted once) and distance / wait matrices.

Pure functions on numpy / scipy graphs, no I/O. A graph is given as directed edge arrays
(src, dst, length_m) over nodes 0..n-1.
"""
import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

JUNCTION_RADIUS_M = 30.0
EPS = 1e-3  # added to every edge so zero-length edges stay in the sparse graph


def junctions(src, dst, length, signal, radius=JUNCTION_RADIUS_M):
    """Junction id per node, -1 = no junction.

    Signal nodes closer than `radius` to each other (path length, ignoring direction) form one junction.
    The nodes on that short path (e.g. a traffic island between two signal crossings) belong to it too.
    Other nodes near a signal do not, so walking along a sidewalk into a junction still pays at the signal.
    """
    n = len(signal)
    jid = np.full(n, -1, dtype=np.int64)
    sig = np.nonzero(signal)[0]
    if len(sig) == 0:
        return jid
    g = csr_matrix((np.asarray(length, dtype=np.float64) + EPS, (src, dst)), shape=(n, n))
    d, pred, owner = dijkstra(g, directed=False, indices=sig, limit=radius,
                              return_predecessors=True, min_only=True)
    # an edge whose two ends belong to different signals joins them when the path through it is short
    a, b = owner[src], owner[dst]
    ok = (a >= 0) & (b >= 0) & (a != b)
    ok[ok] = d[src[ok]] + length[ok] + d[dst[ok]] <= radius
    sig_pos = np.full(n, -1, dtype=np.int64)
    sig_pos[sig] = np.arange(len(sig))
    pairs = coo_matrix((np.ones(ok.sum()), (sig_pos[a[ok]], sig_pos[b[ok]])), shape=(len(sig), len(sig)))
    _, comp = connected_components(pairs, directed=False)
    jid[sig] = comp
    # nodes on the short paths between joined signals: walk both halves back to their signal
    for u, v in zip(src[ok].tolist(), dst[ok].tolist()):
        j = comp[sig_pos[owner[u]]]
        for x in (u, v):
            while x >= 0 and jid[x] != j:
                jid[x] = j
                x = pred[x]
    return jid


def entry_wait(node_wait, jid):
    """Wait paid when a node is entered from outside: its junction's wait (the largest wait of its signals)
    for a junction node, else its own wait."""
    jw = np.zeros(max(int(jid.max()) + 1, 1))
    has = jid >= 0
    np.maximum.at(jw, jid[has], node_wait[has])
    return np.where(has, jw[np.maximum(jid, 0)], node_wait)


def edge_wait(src, dst, node_wait, jid):
    """Wait paid on each directed edge: entry_wait of the target node, but moving between two nodes of
    the same junction is free. So a junction (also entered through an island node) is paid once."""
    jd = jid[dst]
    same = (jd >= 0) & (jid[src] == jd)
    return np.where(same, 0.0, entry_wait(node_wait, jid)[dst]).astype(np.float32)


def access_edges(n, nodes, dist, extra_s_per_m=0.0, owner=None, fixed_s=None, n_points=None, node_entry=None):
    """Virtual nodes that join points to the graph (a multi-source Dijkstra with start costs).

    Point i gets an out-node n + i with edges to its access nodes and an in-node n + P + i with edges from
    them (two nodes, so no path can pass through another point). `nodes` / `dist` are (S, k) arrays, one row
    per access site; an infinite dist means no edge. By default site i = point i. With `owner`, site s belongs
    to point owner[s], so one point can have many sites (a metro platform: all entrances of its station).
    Edge length = straight distance; wait = distance * extra_s_per_m (e.g. the extra time of pushing a bike)
    + fixed_s[s] (e.g. the time to go down to a metro platform). `node_entry` (per graph node, see entry_wait)
    is paid on the edges into the graph, like entering that node from a street: then A -> B and B -> A pay
    the same waits even when a point sits at a signal.
    Returns (src, dst, length, wait, out_ids, in_ids)."""
    s, k = nodes.shape
    owner = np.arange(s) if owner is None else np.asarray(owner)
    fixed = np.zeros(s) if fixed_s is None else np.asarray(fixed_s, dtype=float)
    p = s if n_points is None else n_points
    out_ids, in_ids = n + np.arange(p), n + p + np.arange(p)
    ok = np.isfinite(dist)
    si = np.repeat(np.arange(s), k).reshape(s, k)[ok]
    pi, nd, d = owner[si], nodes[ok], dist[ok]
    ln = np.r_[d, d]
    entry = np.zeros(len(nd)) if node_entry is None else np.asarray(node_entry)[nd]
    wait = ln * extra_s_per_m + np.r_[fixed[si] + entry, fixed[si]]
    return np.r_[out_ids[pi], nd], np.r_[nd, in_ids[pi]], ln, wait, out_ids, in_ids


def save_graph(path, n, src, dst, cost, length, wait, out_ids, in_ids, active):
    """Write the graph for the C++ program (algorithms/router/preprocess/README.md, `graph_<mode>.bin`)."""
    order = np.argsort(src, kind="stable")
    offset = np.r_[0, np.cumsum(np.bincount(src, minlength=n))]
    with open(path, "wb") as f:
        f.write(b"SMG1")
        np.array([n, len(src), len(out_ids)], dtype="<u4").tofile(f)
        for arr, dtype in ((offset, "<u4"), (dst[order], "<u4"), (cost[order], "<f8"), (length[order], "<f4"),
                           (wait[order], "<f4"), (out_ids, "<u4"), (in_ids, "<u4"), (active, "u1")):
            np.asarray(arr).astype(dtype).tofile(f)


class EdgeLookup:
    """Length and wait of the directed edge (u, v), vectorised. Parallel edges: the cheapest one."""

    def __init__(self, src, dst, length, wait, cost, n):
        order = np.lexsort((cost, dst, src))
        key = src[order].astype(np.int64) * n + dst[order]
        first = np.r_[True, key[1:] != key[:-1]]
        self.key, self.length, self.wait, self.n = key[first], length[order][first], wait[order][first], n

    def get(self, u, v):
        i = np.searchsorted(self.key, u.astype(np.int64) * self.n + v)
        return self.length[i], self.wait[i]


def tree_sums(pred, lookup: EdgeLookup):
    """Sum of length and wait from the root to every node of a shortest path tree (pointer jumping).
    Nodes that are not reached get NaN."""
    n = len(pred)
    has = pred >= 0
    length = np.zeros(n)
    wait = np.zeros(n)
    nodes = np.nonzero(has)[0]
    length[nodes], wait[nodes] = lookup.get(pred[nodes], nodes)
    up = np.where(has, pred, -1)
    while True:
        m = up >= 0
        if not m.any():
            break
        i = np.nonzero(m)[0]
        length[i] += length[up[i]]
        wait[i] += wait[up[i]]
        up[i] = up[up[i]]
    return length, wait


def matrix_rows(cost_g, lookup: EdgeLookup, src_nodes, tgt_nodes, src_snap, tgt_snap):
    """Distance (m, incl. snap segments) and wait (s) from each source node to each target node.
    Rows = sources, cols = targets. No path = NaN."""
    dist_out = np.full((len(src_nodes), len(tgt_nodes)), np.nan, dtype=np.float32)
    wait_out = np.full_like(dist_out, np.nan)
    for r, s in enumerate(src_nodes):
        cost, pred = dijkstra(cost_g, indices=int(s), return_predecessors=True)
        length, wait = tree_sums(pred, lookup)
        reach = np.isfinite(cost[tgt_nodes])
        dist_out[r, reach] = length[tgt_nodes[reach]] + src_snap[r] + tgt_snap[reach]
        wait_out[r, reach] = wait[tgt_nodes[reach]]
    return dist_out, wait_out
