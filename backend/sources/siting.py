"""Best place for a new Veturilo station: Warsaw split into hexagons (175 m), each scored with J_synergy
(algorithms/station_siting.py). Lower J = better place.

Inputs per hex (measurements are averaged inside the hex):
- T: car traffic 0..1. MOCK: data/mock/traffic_counts.json (fake counters on OSM roads).
- E: e-scooter trip starts / ends 0..1. MOCK: data/mock/scooter_events.json.gz.
- S: infrastructure safety from OSM tags (length-weighted mean of the street segments in the hex).
- d_net: bike-network distance (m) to the nearest Veturilo station, one multi-source Dijkstra.
City area: the Warsaw boundary from Nominatim (data/geojson/warsaw.geojson).
"""
import gzip
import json
import math
import sys
import threading
from functools import lru_cache

import httpx
import numpy as np
import osmium
from fastapi import APIRouter, Query
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from app.config import settings
from config import DATA, DERIVED, REPO, load_json, save_json, save_npz, to_xy
from sources import nextbike, osm

sys.path.insert(0, str(REPO / "algorithms"))
from station_siting import (  # noqa: E402
    DEFAULTS, HEX_SIZE_M, cost, greedy, hex_grid, hex_of, idw_fill, mean_per_hex, normalize, penalty,
    points_in_rings, weighted_mean_per_hex,
)

BOUNDARY = DATA / "geojson" / "warsaw.geojson"
BOUNDARY_URL = "https://nominatim.openstreetmap.org/lookup"
WARSAW_RELATION = "R336075"
MOCK_DIR = DATA / "mock"
TRAFFIC = MOCK_DIR / "traffic_counts.json"
SCOOTERS = MOCK_DIR / "scooter_events.json.gz"
ROADS = DERIVED / "siting_roads.npz"
HEXES = DERIVED / "siting_hexes.npz"
MAX_R_M = 5000.0  # d_net is computed up to this distance; farther = inf (P is 0 there for any allowed R)
SEED = 20261017
LAT0 = 52.23  # same as config.to_xy
EARTH_R = 6371000.0

# Road classes: used for S and for placing the fake traffic counters.
CLASSES = ["none", "trunk", "primary", "secondary", "tertiary", "local", "bike"]
CAR = {"trunk": 1, "trunk_link": 1, "primary": 2, "primary_link": 2, "secondary": 3, "secondary_link": 3,
       "tertiary": 4, "tertiary_link": 4, "residential": 5, "unclassified": 5, "living_street": 5, "service": 5}
SKIP = {"motorway", "motorway_link", "construction", "proposed", "platform", "raceway", "bus_guideway",
        "elevator", "abandoned", "corridor"}
YES = {"yes", "designated"}
S_PATH, S_LOCAL, S_MAIN, S_MULTI = 0.0, 0.3, 0.6, 1.0


def to_latlon(x, y):
    """Inverse of config.to_xy."""
    lat = np.degrees(np.asarray(y) / EARTH_R)
    lon = np.degrees(np.asarray(x) / (EARTH_R * math.cos(math.radians(LAT0))))
    return lat, lon


# ---------- boundary ----------

def download() -> list[str]:
    """Warsaw admin boundary (simplified polygon) from Nominatim."""
    r = httpx.get(BOUNDARY_URL, params={"osm_ids": WARSAW_RELATION, "polygon_geojson": 1,
                                        "polygon_threshold": 0.0003, "format": "json"},
                  headers={"User-Agent": settings.nominatim_user_agent}, timeout=60)
    r.raise_for_status()
    geo = r.json()[0]["geojson"]
    save_json(BOUNDARY, {"type": "Feature", "properties": {"name": "Warszawa", "osm": WARSAW_RELATION,
                                                           "source": "Nominatim, (c) OpenStreetMap contributors"},
                         "geometry": geo})
    return [BOUNDARY.name]


def boundary_rings() -> list[np.ndarray]:
    """All rings of the boundary in local metres."""
    if not BOUNDARY.exists():
        download()
    geo = load_json(BOUNDARY)["geometry"]
    polys = [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]
    rings = []
    for poly in polys:
        for ring in poly:
            a = np.array(ring, dtype=float)
            x, y = to_xy(a[:, 1], a[:, 0])
            rings.append(np.c_[x, y])
    return rings


# ---------- S from OSM ----------

def road_safety(t) -> tuple[float, int] | None:
    """(S, class index) of one OSM way, None when the way is not a place next to which a station could stand."""
    hw = t.get("highway")
    if hw is None or hw in SKIP:
        return None
    cw = {t.get(k) for k in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both")}
    if hw == "cycleway" or (hw in ("path", "footway", "pedestrian", "track") and t.get("bicycle") in YES) \
            or cw & {"track", "separate"}:
        return S_PATH, CLASSES.index("bike")
    cls = CAR.get(hw)
    if cls is None:  # footways, paths, steps, tracks without bikes: quiet, but no bike infrastructure
        return S_LOCAL, 0
    if cls == 5 or cw & {"lane", "shared_lane", "share_busway", "opposite_lane"}:
        return S_LOCAL, cls
    lanes = t.get("lanes")
    try:
        n = float(lanes.split(";")[0])
        per_dir = n if t.get("oneway") in ("yes", "-1") else n / 2
    except (AttributeError, ValueError):
        per_dir = 2 if cls <= 2 else 1  # no lanes tag: trunk / primary are dual carriageways in Warsaw
    return (S_MULTI if per_dir >= 2 or cls == 1 else S_MAIN), cls


class _RoadHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.lat, self.lon, self.length, self.s, self.cls = [], [], [], [], []

    def way(self, w):
        res = road_safety(w.tags)
        if res is None:
            return
        s, cls = res
        pts = [(n.lat, n.lon) for n in w.nodes if n.location.valid()]
        if len(pts) < 2:
            return
        a = np.array(pts)
        x, y = to_xy(a[:, 0], a[:, 1])
        ln = np.hypot(np.diff(x), np.diff(y))
        self.lat.extend((a[:-1, 0] + a[1:, 0]) / 2)
        self.lon.extend((a[:-1, 1] + a[1:, 1]) / 2)
        self.length.extend(ln)
        self.s.extend([s] * len(ln))
        self.cls.extend([cls] * len(ln))


def roads() -> dict:
    """Street segments (midpoint lat / lon, length m, S, class), one osmium pass, cached."""
    if not ROADS.exists():
        h = _RoadHandler()
        h.apply_file(str(osm.PBF), locations=True)
        save_npz(ROADS, lat=np.array(h.lat), lon=np.array(h.lon), length=np.array(h.length, dtype=np.float32),
                 s=np.array(h.s, dtype=np.float32), cls=np.array(h.cls, dtype=np.int8))
    with np.load(ROADS) as z:
        return {k: z[k] for k in z.files}


# ---------- mocks ----------

HOURLY = np.array([.15, .1, .08, .08, .12, .3, .65, .95, 1.0, .8, .7, .72, .75, .75, .8, .9, .98, 1.0, .85, .65,
                   .5, .4, .3, .2])
PEAK_FLOW = {1: 3200, 2: 1900, 3: 1100, 4: 550, 5: 140}  # cars / h at the peak, by class
COUNTER_WEIGHT = {1: 4.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 0.25}
N_COUNTERS = 1200
N_SCOOTER = 60000
CENTRE = (52.2297, 21.0122)
HOTSPOTS = [  # (name, lat, lon, share)
    ("Centrum / Złote Tarasy", 52.2300, 21.0030, 0.22), ("Politechnika", 52.2196, 21.0108, 0.12),
    ("Kampus UW / Nowy Świat", 52.2400, 21.0180, 0.12), ("Galeria Mokotów", 52.1800, 21.0030, 0.08),
    ("Koneser / Praga", 52.2550, 21.0440, 0.10), ("Bulwary Wiślane", 52.2440, 21.0250, 0.12),
    ("Rondo Daszyńskiego", 52.2300, 20.9840, 0.12), ("Wilanów", 52.1650, 21.0880, 0.06),
    ("Metro Młociny", 52.2900, 20.9300, 0.06),
]


def make_mocks() -> list[str]:
    """Fake traffic counters and e-scooter events (fixed seed). Not real data."""
    rng = np.random.default_rng(SEED)
    rd = roads()
    rx, ry = to_xy(rd["lat"], rd["lon"])
    inside = points_in_rings(rx, ry, boundary_rings())
    # traffic counters on car roads, more on big roads
    w = np.array([COUNTER_WEIGHT.get(int(c), 0.0) for c in range(7)])[rd["cls"]] * rd["length"] * inside
    idx = rng.choice(len(w), size=N_COUNTERS, replace=False, p=w / w.sum())
    counters = []
    for k, i in enumerate(idx):
        cls = int(rd["cls"][i])
        peak = PEAK_FLOW[cls] * rng.lognormal(0, 0.35)
        hourly = peak * HOURLY * (1 + rng.normal(0, 0.08, 24))
        counters.append({"id": f"mock-{k + 1:04d}", "lat": round(float(rd["lat"][i]), 6),
                         "lon": round(float(rd["lon"][i]), 6), "road": CLASSES[cls],
                         "hourly": [int(max(v, 0)) for v in hourly]})
    save_json(TRAFFIC, {"mock": True, "note": "Fake hourly car counts (vehicles / h) for one weekday. Not real data.",
                        "seed": SEED, "counters": counters})
    # e-scooter events: along streets, denser near the centre, plus hotspots
    cx, cy = to_xy(*CENTRE)
    dist_c = np.hypot(rx - cx, ry - cy)
    w = rd["length"] * np.exp(-dist_c / 3500.0) * inside * (rd["cls"] != 1)
    n_street = int(N_SCOOTER * 0.65)
    i = rng.choice(len(w), size=n_street, p=w / w.sum())
    ex, ey = rx[i] + rng.normal(0, 15, n_street), ry[i] + rng.normal(0, 15, n_street)
    shares = np.array([h[3] for h in HOTSPOTS])
    which = rng.choice(len(HOTSPOTS), size=N_SCOOTER - n_street, p=shares / shares.sum())
    hx, hy = to_xy(np.array([h[1] for h in HOTSPOTS]), np.array([h[2] for h in HOTSPOTS]))
    ex = np.r_[ex, hx[which] + rng.normal(0, 300, len(which))]
    ey = np.r_[ey, hy[which] + rng.normal(0, 300, len(which))]
    lat, lon = to_latlon(ex, ey)
    hour = rng.choice(24, size=N_SCOOTER, p=HOURLY / HOURLY.sum())
    kind = rng.integers(0, 2, N_SCOOTER)
    data = {"mock": True, "note": "Fake e-scooter trip starts (kind 0) and ends (kind 1). Not real data.",
            "seed": SEED, "hotspots": [h[0] for h in HOTSPOTS],
            "lat": np.round(lat, 5).tolist(), "lon": np.round(lon, 5).tolist(),
            "kind": kind.tolist(), "hour": hour.tolist()}
    MOCK_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(SCOOTERS, "wt", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    return [TRAFFIC.name, SCOOTERS.name]


def load_scooters() -> dict:
    with gzip.open(SCOOTERS, "rt", encoding="utf-8") as f:
        return json.load(f)


# ---------- network distance ----------

_LOCK = threading.Lock()
_CSR = {}


def bike_csr():
    """Bike graph in metres (ridden + pushed), for scipy."""
    if not _CSR:
        s, d, wm, bm, _, _ = osm.edges("bike")
        n = len(osm.graph()["ids"])
        _CSR["g"] = csr_matrix((wm + bm + osm.EPS, (s, d)), shape=(n, n))
    return _CSR["g"]


def network_distance(sources: np.ndarray, targets: np.ndarray, target_snap: np.ndarray, limit: float) -> np.ndarray:
    """Min bike-network distance (m) from any source node to each target node (+ the target's snap distance)."""
    dist = dijkstra(bike_csr(), directed=True, indices=np.unique(sources), min_only=True, limit=limit)
    return dist[targets] + target_snap


# ---------- hex table ----------

_H = {}


def build() -> dict:
    """Hexes inside Warsaw with T, E, S, d_net. Saved to data/derived/siting_hexes.npz."""
    if not TRAFFIC.exists() or not SCOOTERS.exists():
        make_mocks()
    rings = boundary_rings()
    allx = np.concatenate([r[:, 0] for r in rings])
    ally = np.concatenate([r[:, 1] for r in rings])
    q, r, x, y = hex_grid(allx.min(), ally.min(), allx.max(), ally.max(), HEX_SIZE_M)
    keep = points_in_rings(x, y, rings)
    q, r, x, y = q[keep], r[keep], x[keep], y[keep]
    n = len(q)
    lookup = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(q, r))}

    def index_of(px, py):
        hq, hr = hex_of(px, py, HEX_SIZE_M)
        return np.array([lookup.get((int(a), int(b)), -1) for a, b in zip(hq, hr)], dtype=np.int64)

    # T: mean of the counters' daily mean flow in each hex, empty hexes by IDW
    tc = load_json(TRAFFIC)["counters"]
    cx, cy = to_xy(np.array([c["lat"] for c in tc]), np.array([c["lon"] for c in tc]))
    t_raw, t_n = mean_per_hex(index_of(cx, cy), [np.mean(c["hourly"]) for c in tc], n)
    t_raw = idw_fill(x, y, t_raw)
    # E: scooter events per hex
    sc = load_scooters()
    sx, sy = to_xy(np.array(sc["lat"]), np.array(sc["lon"]))
    _, e_raw = mean_per_hex(index_of(sx, sy), np.ones(len(sx)), n)
    # S: length-weighted mean of the street segments in the hex
    rd = roads()
    rx, ry = to_xy(rd["lat"], rd["lon"])
    s = weighted_mean_per_hex(index_of(rx, ry), rd["s"], rd["length"], n)
    no_streets = np.isnan(s)
    s = np.where(no_streets, S_LOCAL, s)
    # existing stations and d_net
    lat, lon = to_latlon(x, y)
    node, snap = osm.nearest_many(lat, lon, "bike")
    st = nextbike.stations()
    stx, sty = to_xy(np.array([v["lat"] for v in st]), np.array([v["lon"] for v in st]))
    st_hex = index_of(stx, sty)
    stations = np.bincount(st_hex[st_hex >= 0], minlength=n)
    st_node, _ = osm.nearest_many(np.array([v["lat"] for v in st]), np.array([v["lon"] for v in st]), "bike")
    d_net = network_distance(st_node, node, snap, MAX_R_M)
    d_net[stations > 0] = 0.0
    candidate = (stations == 0) & (snap <= HEX_SIZE_M) & ~no_streets
    out = dict(q=q, r=r, x=x, y=y, lat=lat, lon=lon, t_raw=t_raw, t_counters=t_n, t=normalize(t_raw),
               # counts are heavy-tailed (hotspots), so E is normalised on log(1 + count)
               e_raw=e_raw.astype(np.float64), e=normalize(np.log1p(e_raw)), s=s.astype(np.float64), no_streets=no_streets,
               node=node, snap=snap, stations=stations, d_net=d_net, candidate=candidate)
    save_npz(HEXES, **out)
    return out


def hexes(rebuild: bool = False) -> dict:
    with _LOCK:
        if rebuild or not _H:
            if rebuild or not HEXES.exists():
                _H.clear()
                _H.update(build())
            else:
                with np.load(HEXES) as z:
                    _H.update({k: z[k] for k in z.files})
    return _H


def run(n: int = 10, **params) -> list[dict]:
    """Greedy ranking (algorithms/station_siting.greedy) with the bike-network distance update."""
    h = hexes()
    p = {**DEFAULTS, **params}

    def distances_from(i: int) -> np.ndarray:
        return h["snap"][i] + network_distance(np.array([h["node"][i]]), h["node"], h["snap"], p["r"])

    return greedy(h["t"], h["e"], h["s"], h["d_net"], h["candidate"], n, distances_from, p)


def option(h: dict, rank: int, step: dict, p: dict) -> dict:
    i = step["pick"]
    return {"rank": rank, "hex": f"{int(h['q'][i])}:{int(h['r'][i])}", "lat": round(float(h["lat"][i]), 6),
            "lon": round(float(h["lon"][i]), 6), "j": round(step["j"], 4), "t": round(float(h["t"][i]), 4),
            "e": round(float(h["e"][i]), 4), "dNet": None if math.isinf(step["d_net"]) else round(step["d_net"], 1),
            "p": round(float(penalty(step["d_net"], p["r"])), 4), "s": round(float(h["s"][i]), 4)}


@lru_cache(maxsize=32)
def _ranking(n: int, alpha: float, beta: float, gamma: float, delta: float, r: float) -> list[dict]:
    p = {"alpha": alpha, "beta": beta, "gamma": gamma, "delta": delta, "r": r}
    return [option(hexes(), k + 1, step, p) for k, step in enumerate(run(n, **p))]


def warm() -> None:
    hexes()
    bike_csr()


router = APIRouter(prefix="/api/veturilo", tags=["Veturilo (Nextbike GBFS)"])


@router.get("/siting")
def api_siting(n: int = Query(10, ge=1, le=50, description="number of proposals"),
               alpha: float = Query(DEFAULTS["alpha"], ge=0, le=100, description="weight of traffic T"),
               beta: float = Query(DEFAULTS["beta"], ge=0, le=100, description="weight of the station-distance penalty P"),
               gamma: float = Query(DEFAULTS["gamma"], ge=0, le=100, description="weight of safety S"),
               delta: float = Query(DEFAULTS["delta"], ge=0, le=100, description="boost of T by e-scooters E"),
               r: float = Query(DEFAULTS["r"], ge=50, le=MAX_R_M, description="penalty radius R (m)")):
    """Best hexes for new Veturilo stations (lowest J_synergy), picked one by one. T and E are MOCK data."""
    return _ranking(n, alpha, beta, gamma, delta, r)
