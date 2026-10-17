"""OpenStreetMap street graphs for walking and cycling (first / last mile). Transit is NOT taken from
OSM: multimodality is handled by our own algorithms on top of GTFS + GBFS.

Graph: every OSM way node is a vertex, every pair of consecutive nodes on an allowed way is an edge.
Edge cost in seconds = length / speed + expected wait at the target node ("EV wait time").

Expected waits. OSM has no adopted tag for signal timings (only proposals: phases=*, timing=*), so we
use the HCM average delay at a fixed-time signal: d = (C - g)^2 / (2C), C = cycle, g = green.
"""
import sys
import time

import httpx
import numpy as np
import osmium
import osmium.filter
from fastapi import APIRouter, HTTPException, Query
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

from config import BBOX, DERIVED, OSM_DIR, REPO, in_bbox, load_json, save_json, to_xy

sys.path.insert(0, str(REPO / "algorithms"))
from street_graph import StreetGraph  # noqa: E402
from street_model import (  # noqa: E402
    FLAG_ELEVATOR, FLAG_METRO, FLAG_PUSH, FLAG_STEPS, access_edges, access_flags, edge_wait, entry_wait, junctions,
)

EPS = 1e-3  # s added to every scipy edge, so zero-cost edges stay in the sparse matrix

# download() fetches the Geofabrik region (300 MB) once and keeps a small cut of it: the ZTM area (config.BBOX)
# and only the objects we use (see _clip).
PBF = OSM_DIR / "warsaw_ztm.osm.pbf"
URL = "https://download.geofabrik.de/europe/poland/mazowieckie-latest.osm.pbf"
CLIP_KEYS = ("highway", "crossing", "railway", "public_transport", "entrance")

# Default speeds in m/s; the path is chosen with them. A trip has three parts: walk_m / WALK_SPEED[mode]
# + bike_m / BIKE_SPEED + wait_s (a pushed bike walks). Change here for travel profiles.
# accessible: walk without stairs (uses elevators), for a wheelchair. stroller: the same, but also steps with a
# stroller ramp (narrow rails), which are not safe for a wheelchair.
SPEED = {"walk": 1.3, "bike": 4.2, "accessible": 1.3, "stroller": 1.3}
WALK_SPEED = {"walk": SPEED["walk"], "bike": SPEED["walk"], "accessible": SPEED["accessible"],
              "stroller": SPEED["stroller"]}
BIKE_SPEED = SPEED["bike"]
# Modes that cannot use steps (a bike is pushed along the stroller graph): they take elevators.
NO_STEPS = {"bike", "accessible", "stroller"}
# Steps with one of these ramps (=yes) are step-free in the mode. A stroller ramp (two rails / gutters) is not safe
# for a wheelchair, so only the stroller graph (and a pushed bike) takes it. Plain ramp=yes (often bicycle rails)
# is not enough; ramp=separate is a separate way, already in the graph.
RAMP_TAGS = {"accessible": ("ramp:wheelchair",), "stroller": ("ramp:wheelchair", "ramp:stroller")}
# A point (stop, address) joins the graph through up to ACCESS_K nearest nodes that are at most
# ACCESS_EXTRA_M farther than the nearest one. These short segments are walked (a bike is pushed).
ACCESS_K = 6
ACCESS_EXTRA_M = 30
# A metro platform joins the graph through all entrances of its station (GTFS location_type 2);
# entrance <-> platform is a walk of METRO_ACCESS_M (stairs, corridors). Every entrance is assumed to have
# an elevator, which a NO_STEPS mode takes (+ ELEVATOR_S).
METRO_ACCESS_M = 150
# The router fails (422) when the start or the end is farther than this from the graph (m).
MAX_SNAP_M = 1000


def hcm_delay(cycle_s: float, green_s: float) -> float:
    return (cycle_s - green_s) ** 2 / (2 * cycle_s)


# Expected wait (s) when a path enters a node of this kind. Assumed signal plan: 90 s cycle,
# 20 s pedestrian green, 30 s green for vehicles / bikes on the road. An elevator (a highway=elevator node
# or way) costs ELEVATOR_S in every mode: waiting + the ride.
ELEVATOR_S = 60.0
WAIT = {
    "walk": {"crossing_signals": hcm_delay(90, 20), "crossing": 2.0, "traffic_signals": 0.0, "elevator": ELEVATOR_S},
    "bike": {"crossing_signals": hcm_delay(90, 20), "crossing": 0.0, "traffic_signals": hcm_delay(90, 30),
             "elevator": ELEVATOR_S},
}
WAIT["accessible"] = WAIT["stroller"] = WAIT["walk"]
TIMING_TAGS = ("phases", "timing", "cycle_time", "duration", "traffic_signals:phases")

WALK_EXCLUDE = {"abandoned", "bus_guideway", "construction", "motor", "no", "planned", "platform",
                "proposed", "raceway", "razed", "motorway", "motorway_link", "bus_stop", "elevator"}
BIKE_EXCLUDE = {"abandoned", "bus_guideway", "construction", "corridor", "elevator", "escalator", "motor",
                "no", "planned", "platform", "proposed", "raceway", "razed", "steps", "motorway",
                "motorway_link", "trunk", "trunk_link", "bus_stop"}
YES = {"yes", "designated", "permissive"}


def download() -> list[str]:
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    region = OSM_DIR / "region.osm.pbf.tmp"
    with httpx.stream("GET", URL, follow_redirects=True, timeout=600) as r:
        r.raise_for_status()
        with open(region, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    _clip(region, PBF)
    region.unlink()
    return [PBF.name]


def _clip(src, dst) -> None:
    """Keep nodes and ways with a CLIP_KEYS tag inside BBOX (streets, paths, steps, elevators, crossings, stops,
    platforms, metro entrances) and the nodes of those ways. No relations."""
    with osmium.BackReferenceWriter(str(dst), ref_src=str(src), overwrite=True) as w:
        for o in osmium.FileProcessor(str(src)).with_locations().with_filter(osmium.filter.KeyFilter(*CLIP_KEYS)):
            if o.is_node():
                if in_bbox(o.location.lat, o.location.lon):
                    w.add(o)
            elif o.is_way():
                if any(n.location.valid() and in_bbox(n.lat, n.lon) for n in o.nodes):
                    w.add(o)


def _private(t) -> bool:
    return t.get("access") in ("private", "no") or t.get("service") == "private"


def step_free(t, mode: str = "accessible") -> bool:
    """A way without steps, or steps with a ramp the mode can use (RAMP_TAGS)."""
    return t.get("highway") != "steps" or any(t.get(k) == "yes" for k in RAMP_TAGS[mode])


def walk_ok(t) -> bool:
    hw = t.get("highway")
    if hw is None or hw in WALK_EXCLUDE or t.get("area") == "yes" and hw != "pedestrian":
        return False
    if t.get("foot") == "no":
        return False
    if hw == "cycleway" and t.get("foot") not in YES:
        return False
    return not _private(t) or t.get("foot") in YES


def bike_ok(t) -> bool:
    hw = t.get("highway")
    if hw is None or hw in BIKE_EXCLUDE or t.get("area") == "yes":
        return False
    if t.get("bicycle") == "no":
        return False
    if hw in ("footway", "pedestrian") and t.get("bicycle") not in YES:
        return False
    return not _private(t) or t.get("bicycle") in YES


def bike_oneway(t) -> int:
    """1 = forward only, -1 = backward only, 0 = both ways."""
    if t.get("oneway:bicycle") == "no" or (t.get("cycleway") or "").startswith("opposite"):
        return 0
    ow = t.get("oneway")
    if ow in ("yes", "1", "true") or t.get("junction") == "roundabout":
        return 1
    return -1 if ow == "-1" else 0


class _Handler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.special = {}  # node id -> kind
        self.timing_tagged = 0
        self.u, self.v, self.ulat, self.ulon, self.vlat, self.vlon = [], [], [], [], [], []
        self.mode = []  # bit 1 = walk, 2 = bike forward, 4 = bike backward, 8 = accessible walk, 16 = steps,
        # 32 = stroller walk

    def node(self, n):
        t = n.tags
        hw, cr = t.get("highway"), t.get("crossing")
        kind = None
        if cr == "traffic_signals" or t.get("crossing:signals") == "yes":
            kind = "crossing_signals"
        elif hw == "crossing" or cr in ("uncontrolled", "marked", "zebra", "unmarked"):
            kind = "crossing"
        elif hw == "traffic_signals":
            kind = "traffic_signals"
        elif hw == "elevator":
            kind = "elevator"
        if kind:
            self.special[n.id] = kind
            if any(k in t for k in TIMING_TAGS):
                self.timing_tagged += 1

    def way(self, w):
        t = w.tags
        if "highway" not in t:
            return
        walk, bike = walk_ok(t), bike_ok(t)
        hw = t.get("highway")
        lift = hw == "elevator" and not _private(t)
        accessible = (walk and step_free(t, "accessible")) or lift
        stroller = (walk and step_free(t, "stroller")) or lift
        if not (walk or bike or stroller):
            return
        bits = (1 if walk else 0) | (8 if accessible else 0) | (16 if hw == "steps" else 0) | (32 if stroller else 0)
        if bike:
            ow = bike_oneway(t)
            bits |= (2 if ow >= 0 else 0) | (4 if ow <= 0 else 0)
        nodes = [(n.ref, n.lat, n.lon) for n in w.nodes if n.location.valid()]
        for (a, alat, alon), (b, blat, blon) in zip(nodes, nodes[1:]):
            if not (in_bbox(alat, alon) and in_bbox(blat, blon)):
                continue
            self.u.append(a); self.v.append(b)
            self.ulat.append(alat); self.ulon.append(alon); self.vlat.append(blat); self.vlon.append(blon)
            self.mode.append(bits)


def _build() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    h = _Handler()
    h.apply_file(str(PBF), locations=True)
    u, v = np.array(h.u, dtype=np.int64), np.array(h.v, dtype=np.int64)
    ids, inv = np.unique(np.concatenate([u, v]), return_inverse=True)
    ui, vi = inv[: len(u)].astype(np.int32), inv[len(u):].astype(np.int32)
    lat = np.zeros(len(ids)); lon = np.zeros(len(ids))
    lat[ui], lon[ui] = h.ulat, h.ulon
    lat[vi], lon[vi] = h.vlat, h.vlon
    ux, uy = to_xy(np.array(h.ulat), np.array(h.ulon))
    vx, vy = to_xy(np.array(h.vlat), np.array(h.vlon))
    length = np.hypot(ux - vx, uy - vy).astype(np.float32)
    kinds = ["", "crossing_signals", "crossing", "traffic_signals", "elevator"]
    kind = np.zeros(len(ids), dtype=np.int8)
    pos = np.searchsorted(ids, np.fromiter(h.special.keys(), dtype=np.int64, count=len(h.special)))
    found = (pos < len(ids))
    pos_ok = pos[found]
    vals = np.array([kinds.index(k) for k in h.special.values()], dtype=np.int8)[found]
    match = ids[pos_ok] == np.fromiter(h.special.keys(), dtype=np.int64, count=len(h.special))[found]
    kind[pos_ok[match]] = vals[match]
    np.savez_compressed(DERIVED / "osm_graph.npz", ids=ids, lat=lat, lon=lon, u=ui, v=vi, length=length,
                        mode=np.array(h.mode, dtype=np.int8), kind=kind,
                        timing_tagged=np.array([h.timing_tagged]))


_G = {}


def graph() -> dict:
    if not _G:
        cache = DERIVED / "osm_graph.npz"
        if not cache.exists() or (PBF.exists() and PBF.stat().st_mtime > cache.stat().st_mtime):
            _build()  # no cache yet, or a newer .pbf than the cache
        with np.load(DERIVED / "osm_graph.npz") as z:
            _G.update({k: z[k] for k in z.files})
        x, y = to_xy(_G["lat"], _G["lon"])
        _G["tree"] = cKDTree(np.c_[x, y])
    return _G


def node_wait(mode: str) -> np.ndarray:
    g = graph()
    table = np.array([0.0] + [WAIT[mode][k] for k in ("crossing_signals", "crossing", "traffic_signals", "elevator")],
                     dtype=np.float32)
    return table[g["kind"]]


_CSR = {}
_EDGES = {}
_FLAGS = {}


WALK_BIT = {"walk": 1, "accessible": 8, "stroller": 32}  # bit of _Handler.mode per walked graph


def directed_edges(mode: str):
    """(src, dst, length) of the directed graph for a mode."""
    g = graph()
    m = g["mode"]
    if mode in WALK_BIT:
        sel = (m & WALK_BIT[mode]) > 0
        u, v, ln = g["u"][sel], g["v"][sel], g["length"][sel]
        return np.r_[u, v], np.r_[v, u], np.r_[ln, ln]
    fw, bw = (m & 2) > 0, (m & 4) > 0
    return (np.r_[g["u"][fw], g["v"][bw]], np.r_[g["v"][fw], g["u"][bw]],
            np.r_[g["length"][fw], g["length"][bw]])


def edges(mode: str):
    """Directed edges of a mode without parallel duplicates: (src, dst, walk_m, bike_m, wait_s, junction id
    per node). Each edge is either walked or ridden. A signal wait is paid once per junction
    (algorithms/street_model.py); an elevator costs ELEVATOR_S.
    Bike: where riding is not allowed (oneway against, footways, elevators) the bike is pushed along the
    stroller walk graph (no stairs; stroller ramps, which take a bike too): those edges are walked."""
    if mode not in _EDGES:
        g, n = graph(), len(graph()["ids"])
        s, d, ln = directed_edges(mode)
        push = np.zeros(len(s), dtype=bool)
        if mode == "bike":
            ps, pd, pl = directed_edges("stroller")
            s, d, ln, push = np.r_[s, ps], np.r_[d, pd], np.r_[ln, pl], np.r_[push, np.ones(len(ps), dtype=bool)]
        # parallel edges between the same two nodes: riding before pushing, then the shortest
        order = np.lexsort((ln, push, d, s))
        s, d, ln, push = s[order], d[order], ln[order], push[order]
        first = np.r_[True, (s[1:] != s[:-1]) | (d[1:] != d[:-1])]
        s, d, ln, push = s[first], d[first], ln[first], push[first]
        nw = node_wait(mode)
        signal = np.isin(g["kind"], (1, 3)) & (nw > 0)
        jid = junctions(s, d, ln, signal)
        w = edge_wait(s, d, nw, jid)
        lift_way = ((g["mode"] & 8) > 0) & ((g["mode"] & 1) == 0)  # highway=elevator ways (step-free bits only)
        a, b = g["u"][lift_way].astype(np.int64), g["v"][lift_way].astype(np.int64)
        ride = np.isin(s.astype(np.int64) * n + d, np.r_[a * n + b, b * n + a])
        w = np.where(ride, np.maximum(w, WAIT[mode]["elevator"]), w).astype(np.float32)
        elevator = ride | (g["kind"][d] == 4)
        step_way = (g["mode"] & 16) > 0  # highway=steps (also with a ramp: reported, but step-free)
        a, b = g["u"][step_way].astype(np.int64), g["v"][step_way].astype(np.int64)
        stairs = np.isin(s.astype(np.int64) * n + d, np.r_[a * n + b, b * n + a])
        walked = push if mode == "bike" else np.ones(len(s), dtype=bool)
        _FLAGS[mode] = (elevator * FLAG_ELEVATOR | push * FLAG_PUSH | stairs * FLAG_STEPS).astype(np.uint8)
        _EDGES[mode] = (s, d, np.where(walked, ln, 0).astype(np.float32), np.where(walked, 0, ln).astype(np.float32),
                        w, jid)
    return _EDGES[mode]


def edge_flags(mode: str) -> np.ndarray:
    """Per edge of edges(mode): FLAG_ELEVATOR (an elevator node or way), FLAG_PUSH (a pushed bike), FLAG_STEPS."""
    edges(mode)
    return _FLAGS[mode]


def seconds(mode: str, walk_m, bike_m, wait_s):
    """Time with the default speeds of the mode."""
    return walk_m / WALK_SPEED[mode] + bike_m / BIKE_SPEED + wait_s


def csr(mode: str):
    """Sparse cost graph of the street edges (seconds), for scipy."""
    if mode not in _CSR:
        s, d, wm, bm, w, _ = edges(mode)
        n = len(graph()["ids"])
        _CSR[mode] = csr_matrix((seconds(mode, wm, bm, w) + EPS, (s, d)), shape=(n, n))
    return _CSR[mode]


def counts(mode: str) -> dict:
    """Vertices / edges of the raw graph and of the simplified graph (degree-2 chains merged)."""
    s, d, _ = directed_edges(mode)
    used = np.unique(np.r_[s, d])
    if mode != "bike":  # walk graphs are symmetric
        undirected = len(s) // 2
        deg = np.bincount(np.r_[s], minlength=len(graph()["ids"]))  # each undirected edge counted once per end
    else:
        undirected = len({(min(a, b), max(a, b)) for a, b in zip(s.tolist(), d.tolist())})
        pairs = np.unique(np.c_[np.minimum(s, d), np.maximum(s, d)], axis=0)
        deg = np.bincount(pairs.ravel(), minlength=len(graph()["ids"]))
    kind = graph()["kind"]
    removable = (deg == 2) & (kind == 0)
    return {
        "vertices": int(len(used)),
        "edges_undirected": int(undirected),
        "edges_directed": int(len(s)),
        "simplified_vertices": int(len(used) - removable.sum()),
        "simplified_edges_undirected": int(undirected - removable.sum()),
        "signal_crossings": int(((kind == 1) & np.isin(np.arange(len(kind)), used)).sum()),
        "other_crossings": int(((kind == 2) & np.isin(np.arange(len(kind)), used)).sum()),
        "road_signals": int(((kind == 3) & np.isin(np.arange(len(kind)), used)).sum()),
    }


def nearest(lat: float, lon: float, mode: str | None = None) -> tuple[int, float]:
    """Nearest graph node (index, distance m). With a mode: only nodes of that mode's main component."""
    g = graph()
    x, y = to_xy(np.array([lat]), np.array([lon]))
    if mode is None:
        dist, idx = g["tree"].query(np.c_[x, y])
        return int(idx[0]), float(dist[0])
    nodes, tree = _mode_tree(mode)
    dist, idx = tree.query(np.c_[x, y])
    return int(nodes[idx[0]]), float(dist[0])


def nearest_many(lat, lon, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """nearest() for arrays of points: (node indices, distances m)."""
    nodes, tree = _mode_tree(mode)
    x, y = to_xy(np.asarray(lat), np.asarray(lon))
    dist, idx = tree.query(np.c_[x, y])
    return nodes[idx], dist


def access(lat, lon, mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Access nodes of points: (nodes, distances m), both (P, ACCESS_K); an unused slot has distance inf."""
    nodes, tree = _mode_tree(mode)
    x, y = to_xy(np.atleast_1d(np.asarray(lat, dtype=float)), np.atleast_1d(np.asarray(lon, dtype=float)))
    dist, idx = tree.query(np.c_[x, y], k=ACCESS_K)
    return nodes[idx], np.where(dist <= dist[:, :1] + ACCESS_EXTRA_M, dist, np.inf)


def points_graph(lat, lon, mode: str, entrances=None, transfers=()) -> StreetGraph:
    """The street graph of a mode + a virtual out node and in node per point (see street_model.access_edges).
    The access segments are walked. `entrances[i]`: a list of (lat, lon) for a metro platform; it joins through
    all of them, + METRO_ACCESS_M walked (+ an elevator in a NO_STEPS mode); empty for any other point.
    `transfers`: (i, j, walk_m) in-station transfers between two points (metro platforms): an edge out_i -> in_j
    walked, + an elevator in a NO_STEPS mode. A point farther than MAX_SNAP_M from the graph is not active."""
    s, d, wm, bm, w, jid = edges(mode)
    n, p = len(graph()["ids"]), len(lat)
    entrances = entrances or [[]] * p
    sites = [(i, la, lo, False) for i, (la, lo, ent) in enumerate(zip(lat, lon, entrances)) if not ent]
    sites += [(i, la, lo, True) for i, ent in enumerate(entrances) for la, lo in ent]
    owner, slat, slon, metro = (np.array(x) for x in zip(*sites))
    lift = mode in NO_STEPS  # every metro entrance is assumed to have an elevator
    an, ad = access(slat, slon, mode)
    vs, vd, vw_m, vwait, out_node, in_node = access_edges(
        n, an, ad, owner=owner.astype(int), fixed_m=metro * METRO_ACCESS_M, fixed_s=metro * lift * ELEVATOR_S,
        n_points=p, node_entry=entry_wait(node_wait(mode), jid))
    site_flags = np.where(metro, FLAG_METRO | (FLAG_ELEVATOR if lift else 0), 0)
    ts = np.array([out_node[i] for i, _, _ in transfers], dtype=int)
    td = np.array([in_node[j] for _, j, _ in transfers], dtype=int)
    tm = np.array([m for _, _, m in transfers], dtype=float)
    tw = np.full(len(transfers), ELEVATOR_S if lift else 0.0)
    tf = np.full(len(transfers), FLAG_METRO | (FLAG_ELEVATOR if lift else 0), dtype=np.uint8)
    usable = np.zeros(n + 2 * p, dtype=bool)
    usable[_mode_tree(mode)[0]] = True
    return StreetGraph(walk_speed=WALK_SPEED[mode], bike_speed=BIKE_SPEED, access_k=ACCESS_K,
                       access_extra_m=ACCESS_EXTRA_M, max_snap_m=MAX_SNAP_M,
                       src=np.r_[s, vs, ts], dst=np.r_[d, vd, td], walk=np.r_[wm, vw_m, tm],
                       bike=np.r_[bm, np.zeros(len(vs) + len(ts))], wait=np.r_[w, vwait, tw],
                       flags=np.r_[edge_flags(mode), access_flags(ad, site_flags), tf],
                       lon=np.r_[graph()["lon"], lon, lon], lat=np.r_[graph()["lat"], lat, lat], usable=usable,
                       entry_wait=np.r_[entry_wait(node_wait(mode), jid), np.zeros(2 * p)],
                       out_node=out_node, in_node=in_node, active=nearest_many(lat, lon, mode)[1] <= MAX_SNAP_M)


_USABLE = {}


def _mode_tree(mode: str):
    """KD-tree over the largest strongly connected component of a mode (snapping elsewhere = dead end)."""
    if mode not in _USABLE:
        _, labels = connected_components(csr(mode), directed=True, connection="strong")
        nodes = np.nonzero(labels == np.bincount(labels).argmax())[0]
        x, y = to_xy(graph()["lat"][nodes], graph()["lon"][nodes])
        _USABLE[mode] = (nodes, cKDTree(np.c_[x, y]))
    return _USABLE[mode]


def benchmark(points: list[tuple[float, float]], mode: str, sample: int = 50, limit_s: float | None = None,
              seed: int = 1) -> dict:
    """Item 4: time one-to-all Dijkstra from `sample` random points, extrapolate to all points."""
    rng = np.random.default_rng(seed)
    snapped = np.array([nearest(lat, lon, mode)[0] for lat, lon in points])
    pick = rng.choice(len(snapped), size=min(sample, len(snapped)), replace=False)
    cost_g = csr(mode)
    t0 = time.perf_counter()
    dist = dijkstra(cost_g, indices=snapped[pick], limit=limit_s if limit_s else np.inf)
    per_source = (time.perf_counter() - t0) / len(pick)
    reach = np.isfinite(dist[:, snapped]).sum(axis=1)
    n = len(points)
    return {"mode": mode, "points": n, "sample_sources": int(len(pick)), "limit_s": limit_s,
            "seconds_per_source": round(per_source, 3),
            "all_pairs_hours_1_core": round(per_source * n / 3600, 4),
            "avg_points_reached": round(float(reach.mean()), 1),
            "pairs_to_store": int(reach.mean() * n),
            "dense_matrix_mb_float32": round(n * n * 4 / 1e6, 1)}


# ---------------------------------------------------------------- API

router = APIRouter(prefix="/api/osm", tags=["OSM street graph"])


def check_mode(mode: str) -> None:
    if mode not in SPEED:
        raise HTTPException(400, "mode must be walk, bike, accessible or stroller")


@router.get("/graph/summary")
def api_summary(mode: str = Query("walk", description="walk, bike, accessible or stroller")):
    """Vertex / edge / crossing counts of the walk, bike, accessible or stroller graph, speeds and waits."""
    check_mode(mode)
    return {**counts(mode), "speed_m_s": SPEED[mode], "waits_s": WAIT[mode],
            "nodes_with_signal_timing_tags": int(graph()["timing_tagged"][0])}


@router.get("/nearest")
def api_nearest(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                mode: str = "walk"):
    """Nearest node of the walk / bike graph to a point."""
    check_mode(mode)
    i, d = nearest(lat, lon, mode)
    g = graph()
    return {"node": int(g["ids"][i]), "lat": float(g["lat"][i]), "lon": float(g["lon"][i]), "distance_m": d}


TRANSPORT_TAGS = ("public_transport", "railway", "highway", "ref", "local_ref", "name", "level", "wheelchair",
                  "bus", "tram", "train", "subway", "entrance")


def transport_objects() -> dict:
    """OSM transport objects for the station mapping (backend/stations.py), cached in data/derived/:
    {"nodes": [...], "ways": [...]}. Nodes: platforms / stop positions / bus stops / entrances / stations with their
    tags. Ways: platforms with their node coordinates. Rebuilt when the .pbf is newer than the cache."""
    cache = DERIVED / "osm_transport.json"
    if cache.exists() and cache.stat().st_mtime >= PBF.stat().st_mtime:
        return load_json(cache)
    nodes, ways = [], []
    for o in osmium.FileProcessor(str(PBF)).with_locations():
        t = o.tags
        if o.is_node():
            if (t.get("public_transport") in ("platform", "stop_position") or t.get("highway") == "bus_stop"
                    or t.get("railway") in ("subway_entrance", "tram_stop", "station", "halt", "platform")):
                nodes.append({"id": o.id, "lat": o.location.lat, "lon": o.location.lon,
                              "tags": {k: t[k] for k in TRANSPORT_TAGS if k in t}})
        elif o.is_way() and (t.get("railway") == "platform" or t.get("public_transport") == "platform"):
            coords = [[n.lat, n.lon] for n in o.nodes if n.location.valid()]
            if coords:
                ways.append({"id": o.id, "coords": coords, "tags": {k: t[k] for k in TRANSPORT_TAGS if k in t}})
    out = {"nodes": nodes, "ways": ways}
    save_json(cache, out)
    return out


def warm() -> None:
    """Build the graph and the mode indexes. Called once at server start (main.py)."""
    graph()
    for mode in SPEED:
        _mode_tree(mode)


def snap_distances(points: list[tuple[float, float]], mode: str) -> np.ndarray:
    """Distance (m) from each (lat, lon) to the nearest usable node of the mode (used by report.py)."""
    return nearest_many([p[0] for p in points], [p[1] for p in points], mode)[1]
