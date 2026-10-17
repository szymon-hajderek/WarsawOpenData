"""Street cost model: signal junctions (a junction's wait is paid once) and how points join the graph.

Pure numpy / scipy functions, no I/O. Edges are directed arrays (src, dst, length_m) over nodes 0..n-1.
Used by backend/sources/osm.py to build the street graph; the search itself is the C++ program
(algorithms/router/preprocess/).
"""
import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

JUNCTION_RADIUS_M = 30.0
# Edge flags (graph file, path output): an elevator ride, a pushed bike, a point's access segment, a metro entrance.
FLAG_ELEVATOR, FLAG_PUSH, FLAG_ACCESS, FLAG_METRO = 1, 2, 4, 8


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
    # +1 mm keeps zero-length edges in the sparse matrix
    g = csr_matrix((np.asarray(length, dtype=np.float64) + 1e-3, (src, dst)), shape=(n, n))
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


def access_edges(n, nodes, dist, owner=None, fixed_m=None, fixed_s=None, n_points=None, node_entry=None):
    """Virtual nodes that join points to the graph (a multi-source Dijkstra with start costs).

    Point i gets an out-node n + i with edges to its access nodes and an in-node n + P + i with edges from
    them (two nodes, so no path can pass through another point). `nodes` / `dist` are (S, k) arrays, one row
    per access site; an infinite dist means no edge. By default site i = point i. With `owner`, site s belongs
    to point owner[s], so one point can have many sites (a metro platform: all entrances of its station).
    These segments are walked: walk_m = straight distance + fixed_m[s] (e.g. the walk down to a metro platform);
    wait = fixed_s[s] (e.g. an elevator). `node_entry` (per graph node, see entry_wait) is paid on the edges
    into the graph, like entering that node from a street: then A -> B and B -> A pay the same waits even when
    a point sits at a signal.
    Returns (src, dst, walk_m, wait, out_ids, in_ids)."""
    s, k = nodes.shape
    owner = np.arange(s) if owner is None else np.asarray(owner)
    fixed_m = np.zeros(s) if fixed_m is None else np.asarray(fixed_m, dtype=float)
    fixed_s = np.zeros(s) if fixed_s is None else np.asarray(fixed_s, dtype=float)
    p = s if n_points is None else n_points
    out_ids, in_ids = n + np.arange(p), n + p + np.arange(p)
    ok = np.isfinite(dist)
    si = np.repeat(np.arange(s), k).reshape(s, k)[ok]
    pi, nd, d = owner[si], nodes[ok], dist[ok]
    walk = np.r_[d + fixed_m[si], d + fixed_m[si]]
    entry = np.zeros(len(nd)) if node_entry is None else np.asarray(node_entry)[nd]
    wait = np.r_[fixed_s[si] + entry, fixed_s[si]]
    return np.r_[out_ids[pi], nd], np.r_[nd, in_ids[pi]], walk, wait, out_ids, in_ids


def access_flags(dist, site_flags):
    """Flags of the edges made by access_edges, in the same order: FLAG_ACCESS | site_flags[site]."""
    s, k = dist.shape
    si = np.repeat(np.arange(s), k).reshape(s, k)[np.isfinite(dist)]
    f = FLAG_ACCESS | np.asarray(site_flags, dtype=np.uint8)[si]
    return np.r_[f, f].astype(np.uint8)
